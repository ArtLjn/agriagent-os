import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const VERTEX_SHADER = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform sampler2D uImage;
uniform vec2 uPlaneSizes;
uniform vec2 uImageSizes;
uniform vec2 uResolution;
uniform float uScrollSpeed;
varying vec2 vUv;

void main() {
  vec2 ratio = vec2(
    min((uPlaneSizes.x / uPlaneSizes.y) / (uImageSizes.x / uImageSizes.y), 1.0),
    min((uPlaneSizes.y / uPlaneSizes.x) / (uImageSizes.y / uImageSizes.x), 1.0)
  );
  vec2 uv = vec2(
    vUv.x * ratio.x + (1.0 - ratio.x) * 0.5,
    vUv.y * ratio.y + (1.0 - ratio.y) * 0.5
  );
  vec2 pixel = floor(uv * uResolution) / uResolution + 0.5 / uResolution;
  vec3 color = texture2D(uImage, pixel).rgb;
  gl_FragColor = vec4(color, 1.0);
}
`;

export default function CropManagementSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const uniformsRef = useRef<Record<string, THREE.IUniform> | null>(null);

  useEffect(() => {
    const container = canvasContainerRef.current;
    if (!container) return;

    // Three.js setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, container.offsetWidth / container.offsetHeight, 0.1, 100);
    camera.position.z = 5;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(container.offsetWidth, container.offsetHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Load texture
    const loader = new THREE.TextureLoader();
    loader.load('/feature-crop-cycle.jpg', (texture) => {
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;

      const img = texture.image as HTMLImageElement;
      const imgAspect = img.naturalWidth / img.naturalHeight;

      // Calculate plane size to fill container width (90%)
      const containerWidth = container.offsetWidth * 0.9;
      const planeHeight = containerWidth / imgAspect / (container.offsetWidth / container.offsetHeight) * 2.5;
      const planeWidth = planeHeight * imgAspect;

      const geometry = new THREE.PlaneGeometry(planeWidth, planeHeight);
      const uniforms = {
        uImage: { value: texture },
        uPlaneSizes: { value: new THREE.Vector2(planeWidth, planeHeight) },
        uImageSizes: { value: new THREE.Vector2(img.naturalWidth, img.naturalHeight) },
        uResolution: { value: new THREE.Vector2(100, 100) },
        uScrollSpeed: { value: 0.0 },
      };
      uniformsRef.current = uniforms;

      const material = new THREE.ShaderMaterial({
        vertexShader: VERTEX_SHADER,
        fragmentShader: FRAGMENT_SHADER,
        uniforms,
      });

      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      // ScrollTrigger for pixelation transition
      gsap.to(uniforms.uResolution.value, {
        x: 500,
        y: 500,
        scrollTrigger: {
          trigger: container,
          start: 'top 80%',
          end: 'bottom 20%',
          scrub: 1.0,
        },
      });
    });

    // Animation loop
    let animId: number;
    function animate() {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    }
    animate();

    // Resize
    function onResize() {
      if (!container || !renderer) return;
      const w = container.offsetWidth;
      const h = container.offsetHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    window.addEventListener('resize', onResize);

    // Title animation
    const ctx = gsap.context(() => {
      gsap.from('.crop-title', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: sectionRef.current,
          start: 'top 80%',
        },
      });
    });

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      ctx.revert();
    };
  }, []);

  return (
    <section
      ref={sectionRef}
      className="section-padding bg-[#013A33] overflow-hidden"
    >
      <div className="container-main">
        {/* Header */}
        <div className="crop-title text-center mb-12">
          <p className="text-white/60 text-xs font-medium uppercase tracking-[0.1em] mb-4">
            种植管理
          </p>
          <h2
            className="text-white font-semibold tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all' }}
          >
            从播种到收获，全程数字化追踪
          </h2>
          <p className="text-white/60 text-base max-w-[520px] mx-auto leading-relaxed" style={{ wordBreak: 'keep-all' }}>
            为每一块田地建立数字档案，管理作物模板、种植周期、田间活动。让农事管理像查看日历一样简单。
          </p>
        </div>

        {/* Three.js Canvas Container */}
        <div
          ref={canvasContainerRef}
          className="w-full rounded-sm-card overflow-hidden"
          style={{ height: 'clamp(300px, 50vw, 600px)' }}
        />

        {/* CTA */}
        <div className="text-center mt-10">
          <button className="px-8 py-4 bg-transparent text-white font-semibold text-base rounded-pill border border-white/30 hover:bg-white/10 transition-all duration-200">
            了解种植管理
          </button>
        </div>
      </div>
    </section>
  );
}
