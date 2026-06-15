import { useEffect, useRef, useState } from 'react';

const VERTEX_SHADER = `
attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const SIMULATION_FRAGMENT = `
precision mediump float;
uniform vec2 u_resolution;
uniform sampler2D u_previousState;
uniform vec2 u_mouse;
uniform vec2 u_mouseDelta;
uniform float u_pointerStrength;
uniform float u_dt;

vec3 encodeState(vec2 vel, float ink) {
  return vec3(vel.x, vel.y, ink);
}

vec3 decodeState(vec3 raw) {
  return vec3((raw.x - 0.5) * 0.8, (raw.y - 0.5) * 0.8, raw.z);
}

float lineDistance(vec2 p, vec2 a, vec2 b) {
  vec2 ab = b - a;
  float l2 = dot(ab, ab);
  if (l2 < 0.0001) return distance(p, a);
  float t = clamp(dot(p - a, ab) / l2, 0.0, 1.0);
  return distance(p, a + t * ab);
}

void main() {
  vec2 pixel = gl_FragCoord.xy;
  vec2 texel = 1.0 / u_resolution;

  vec2 uvL = (gl_FragCoord.xy - vec2(texel.x, 0.0)) / u_resolution;
  vec2 uvR = (gl_FragCoord.xy + vec2(texel.x, 0.0)) / u_resolution;
  vec2 uvU = (gl_FragCoord.xy + vec2(0.0, texel.y)) / u_resolution;
  vec2 uvD = (gl_FragCoord.xy - vec2(0.0, texel.y)) / u_resolution;

  vec3 prev = decodeState(texture2D(u_previousState, gl_FragCoord.xy / u_resolution).rgb);
  vec3 stateL = decodeState(texture2D(u_previousState, uvL).rgb);
  vec3 stateR = decodeState(texture2D(u_previousState, uvR).rgb);
  vec3 stateU = decodeState(texture2D(u_previousState, uvU).rgb);
  vec3 stateD = decodeState(texture2D(u_previousState, uvD).rgb);

  vec2 vel = prev.xy;
  float ink = prev.z;

  float gradInkX = (stateR.z - stateL.z) * 0.5;
  float gradInkY = (stateU.z - stateD.z) * 0.5;

  vec2 advUV = (gl_FragCoord.xy - vel * u_dt) / u_resolution;
  vec3 advectedRaw = texture2D(u_previousState, advUV).rgb;
  vec3 advected = decodeState(advectedRaw);

  vel = mix(vel, (stateL.xy + stateR.xy + stateU.xy + stateD.xy) * 0.25, 0.15);
  ink = mix(ink, (stateL.z + stateR.z + stateU.z + stateD.z) * 0.25, 0.1);

  float div = (stateR.x - stateL.x + stateU.y - stateD.y);
  vel -= vec2(gradInkX, gradInkY) * 0.01;
  vel -= div * 0.05;

  vec2 pixelUV = pixel / u_resolution;
  float mouseDist = lineDistance(pixelUV, u_mouse, u_mouse - u_mouseDelta * 10.0);
  float strength = exp(-mouseDist * mouseDist * u_pointerStrength);
  vel += u_mouseDelta * strength * (10.0 * u_dt);
  ink += strength * (2.0 * u_dt);

  vel *= 0.985;
  ink *= 0.985;

  vel = clamp(vel, vec2(-0.4), vec2(0.4));
  ink = clamp(ink, 0.0, 1.0);

  gl_FragColor = vec4(vel.x / 0.8 + 0.5, vel.y / 0.8 + 0.5, ink, 1.0);
}
`;

const DISPLAY_FRAGMENT = `
precision mediump float;
uniform vec2 u_resolution;
uniform sampler2D u_state;
uniform float u_colorCycleSpeed;

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  vec3 raw = texture2D(u_state, uv).rgb;
  float ink = raw.z;
  float velMag = length((raw.xy - 0.5) * 0.8);
  float colorAngle = atan((raw.y - 0.5) * 0.8, (raw.x - 0.5) * 0.8) + 3.14159;
  float cyclingHue = fract(colorAngle / 6.28318 + u_colorCycleSpeed);
  vec3 baseColor = mix(vec3(0.75, 1.0, 0.0), vec3(0.133, 0.682, 0.82), cyclingHue);
  float intensity = ink * 1.2 + velMag * 0.5;
  vec3 color = baseColor * intensity;
  vec3 bg = vec3(0.004, 0.227, 0.2);
  vec3 final_color = bg + color;
  float vignette = 1.0 - dot(uv - 0.5, uv - 0.5) * 0.8;
  gl_FragColor = vec4(final_color * vignette, 1.0);
}
`;

function createShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error('Shader compile error:', gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl: WebGLRenderingContext, vs: string, fs: string): WebGLProgram | null {
  const vert = createShader(gl, gl.VERTEX_SHADER, vs);
  const frag = createShader(gl, gl.FRAGMENT_SHADER, fs);
  if (!vert || !frag) return null;
  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vert);
  gl.attachShader(program, frag);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error('Program link error:', gl.getProgramInfoLog(program));
    return null;
  }
  return program;
}

function createFBO(gl: WebGLRenderingContext, w: number, h: number) {
  const texture = gl.createTexture()!;
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const fbo = gl.createFramebuffer()!;
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
  return { fbo, texture, w, h };
}

export default function HeroSection() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const mouseRef = useRef({ x: 0.5, y: 0.5, prevX: 0.5, prevY: 0.5, deltaX: 0, deltaY: 0, history: Array(5).fill({ x: 0.5, y: 0.5 }) });
  const pointerStrengthRef = useRef(2800.0);
  const colorCycleRef = useRef(0.0);
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext('webgl', { alpha: false, premultipliedAlpha: false });
    if (!gl) return;

    const isMobile = window.innerWidth < 768;
    const SIM_SIZE = isMobile ? 128 : 256;

    function resize() {
      if (!canvas) return;
      const dpr = Math.min(window.devicePixelRatio, isMobile ? 1 : 1.5);
      canvas.width = canvas.offsetWidth * dpr;
      canvas.height = canvas.offsetHeight * dpr;
    }
    resize();
    window.addEventListener('resize', resize);

    const simProg = createProgram(gl, VERTEX_SHADER, SIMULATION_FRAGMENT);
    const dispProg = createProgram(gl, VERTEX_SHADER, DISPLAY_FRAGMENT);
    if (!simProg || !dispProg) return;

    // Fullscreen quad
    const quadBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);

    // FBOs
    let fbo0 = createFBO(gl, SIM_SIZE, SIM_SIZE);
    let fbo1 = createFBO(gl, SIM_SIZE, SIM_SIZE);

    function bindQuad(prog: WebGLProgram) {
      const loc = gl!.getAttribLocation(prog, 'a_position');
      gl!.bindBuffer(gl!.ARRAY_BUFFER, quadBuf);
      gl!.enableVertexAttribArray(loc);
      gl!.vertexAttribPointer(loc, 2, gl!.FLOAT, false, 0, 0);
    }

    function render() {
      if (!gl || !simProg || !dispProg) return;
      const mouse = mouseRef.current;

      // Smooth mouse velocity
      const hx = mouse.history.map(h => h.x);
      const hy = mouse.history.map(h => h.y);
      const avgX = hx.reduce((a, b) => a + b, 0) / hx.length;
      const avgY = hy.reduce((a, b) => a + b, 0) / hy.length;

      mouse.deltaX = (mouse.x - avgX) * 0.5;
      mouse.deltaY = (mouse.y - avgY) * 0.5;

      colorCycleRef.current += 0.0008;

      // Simulation pass
      gl.bindFramebuffer(gl.FRAMEBUFFER, fbo1.fbo);
      gl.viewport(0, 0, SIM_SIZE, SIM_SIZE);
      gl.useProgram(simProg);
      bindQuad(simProg);

      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, fbo0.texture);
      gl.uniform1i(gl.getUniformLocation(simProg, 'u_previousState'), 0);
      gl.uniform2f(gl.getUniformLocation(simProg, 'u_resolution'), SIM_SIZE, SIM_SIZE);
      gl.uniform2f(gl.getUniformLocation(simProg, 'u_mouse'), mouse.x, mouse.y);
      gl.uniform2f(gl.getUniformLocation(simProg, 'u_mouseDelta'), mouse.deltaX, mouse.deltaY);
      gl.uniform1f(gl.getUniformLocation(simProg, 'u_pointerStrength'), pointerStrengthRef.current);
      gl.uniform1f(gl.getUniformLocation(simProg, 'u_dt'), 0.016);

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

      // Display pass
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, canvas!.width, canvas!.height);
      gl.useProgram(dispProg);
      bindQuad(dispProg);

      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, fbo1.texture);
      gl.uniform1i(gl.getUniformLocation(dispProg, 'u_state'), 0);
      gl.uniform2f(gl.getUniformLocation(dispProg, 'u_resolution'), canvas!.width, canvas!.height);
      gl.uniform1f(gl.getUniformLocation(dispProg, 'u_colorCycleSpeed'), colorCycleRef.current);

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

      // Swap
      const tmp = fbo0; fbo0 = fbo1; fbo1 = tmp;

      // Update history
      mouse.history.shift();
      mouse.history.push({ x: mouse.x, y: mouse.y });

      animRef.current = requestAnimationFrame(render);
    }

    animRef.current = requestAnimationFrame(render);

    // Entrance animation
    setTimeout(() => setEntered(true), 100);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
      gl.deleteProgram(simProg);
      gl.deleteProgram(dispProg);
      gl.deleteFramebuffer(fbo0.fbo);
      gl.deleteFramebuffer(fbo1.fbo);
      gl.deleteTexture(fbo0.texture);
      gl.deleteTexture(fbo1.texture);
    };
  }, []);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      mouseRef.current.prevX = mouseRef.current.x;
      mouseRef.current.prevY = mouseRef.current.y;
      mouseRef.current.x = e.clientX / window.innerWidth;
      mouseRef.current.y = 1.0 - e.clientY / window.innerHeight;
    }
    function onTouchMove(e: TouchEvent) {
      const t = e.touches[0];
      mouseRef.current.x = t.clientX / window.innerWidth;
      mouseRef.current.y = 1.0 - t.clientY / window.innerHeight;
    }
    function onClick() {
      pointerStrengthRef.current = pointerStrengthRef.current === 2800.0 ? 1400.0 : 2800.0;
    }
    window.addEventListener('mousemove', onMouseMove, { passive: true });
    window.addEventListener('touchmove', onTouchMove, { passive: true });
    window.addEventListener('click', onClick);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('click', onClick);
    };
  }, []);

  const scrollTo = (id: string) => {
    const el = document.querySelector(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section id="hero" className="relative w-full min-h-[100dvh] flex items-center justify-center overflow-hidden bg-primary-dark">
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', zIndex: 0 }}
      />
      <div className="relative z-10 text-center px-6 max-w-3xl mx-auto pointer-events-none" style={{ pointerEvents: 'none' }}>
        {/* Eyebrow */}
        <p
          className="text-accent-lime text-xs sm:text-sm font-medium uppercase tracking-[0.1em] mb-6"
          style={{
            opacity: entered ? 1 : 0,
            transform: entered ? 'translateY(0)' : 'translateY(20px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s',
          }}
        >
          AI 驱动的智慧农场经营管理平台
        </p>
        {/* Headline Line 1 */}
        <h1
          className="text-white font-bold leading-[0.95] tracking-[-0.01em]"
          style={{
            fontSize: 'clamp(3rem, 8vw, 7rem)',
            opacity: entered ? 1 : 0,
            transform: entered ? 'translateY(0)' : 'translateY(40px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.5s',
          }}
        >
          智慧农场
        </h1>
        {/* Headline Line 2 */}
        <h1
          className="text-accent-lime font-bold leading-[0.95] tracking-[-0.01em] mb-6"
          style={{
            fontSize: 'clamp(3rem, 8vw, 7rem)',
            opacity: entered ? 1 : 0,
            transform: entered ? 'translateY(0)' : 'translateY(40px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.7s',
          }}
        >
          经营管理
        </h1>
        {/* Subheadline */}
        <p
          className="text-white/80 text-base sm:text-lg max-w-[560px] mx-auto mb-8 leading-relaxed"
          style={{
            opacity: entered ? 1 : 0,
            transition: 'opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.9s',
          }}
        >
          用 AI 管理种植周期、账务成本、农事日志和经营决策。让每一寸土地的数据都为你创造收益。
        </p>
        {/* CTA Group */}
        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
          style={{
            opacity: entered ? 1 : 0,
            transition: 'opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1.1s',
            pointerEvents: 'auto',
          }}
        >
          <button
            onClick={() => scrollTo('#download')}
            className="px-8 py-4 bg-accent-lime text-primary-dark font-semibold text-base rounded-pill hover:scale-[1.03] hover:brightness-105 transition-all duration-200"
            style={{ pointerEvents: 'auto' }}
          >
            立即下载
          </button>
          <button
            onClick={() => scrollTo('#features')}
            className="px-8 py-4 bg-transparent text-white font-semibold text-base rounded-pill border border-white/40 hover:bg-white/10 transition-all duration-200"
            style={{ pointerEvents: 'auto' }}
          >
            查看功能
          </button>
        </div>

        {/* Scroll indicator */}
        <div
          className="mt-16 flex flex-col items-center gap-2"
          style={{
            opacity: entered ? 1 : 0,
            transition: 'opacity 1s ease 1.5s',
          }}
        >
          <div className="animate-bounce">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white/40">
              <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="text-white/30 text-xs">scroll to explore</span>
        </div>
      </div>
    </section>
  );
}
