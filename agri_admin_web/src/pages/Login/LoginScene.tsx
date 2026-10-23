export type LoginTheme = 'light' | 'dark';

function DayScene() {
  return (
    <svg
      className="login-scene"
      viewBox="0 0 900 600"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <filter id="login-sun-soft" x="-90%" y="-90%" width="280%" height="280%">
          <feGaussianBlur stdDeviation="26" />
        </filter>
        <linearGradient id="login-hill-far" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a9d5b5" />
          <stop offset="100%" stopColor="#7fb992" />
        </linearGradient>
        <linearGradient id="login-hill-mid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6cb287" />
          <stop offset="100%" stopColor="#4a9068" />
        </linearGradient>
        <linearGradient id="login-hill-near" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4f9d6c" />
          <stop offset="100%" stopColor="#3a7f5a" />
        </linearGradient>
        <filter id="login-soft-blur" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>

      <g className="login-scene__sun">
        <circle cx="704" cy="118" r="76" fill="#ffe9ad" opacity="0.55" filter="url(#login-sun-soft)" />
        <circle cx="704" cy="118" r="44" fill="#ffeec0" opacity="0.65" filter="url(#login-sun-soft)" />
        <circle cx="704" cy="118" r="30" fill="#fff4c9" />
      </g>

      <g className="login-scene__clouds">
        <g fill="#ffffff" filter="url(#login-soft-blur)">
          <g className="login-cloud login-cloud--a" opacity="0.78">
            <ellipse cx="228" cy="146" rx="92" ry="25" />
            <ellipse cx="284" cy="130" rx="54" ry="21" />
            <ellipse cx="172" cy="134" rx="42" ry="17" />
          </g>
          <g className="login-cloud login-cloud--b" opacity="0.58">
            <ellipse cx="600" cy="100" rx="68" ry="19" />
            <ellipse cx="648" cy="90" rx="40" ry="15" />
          </g>
          <g className="login-cloud login-cloud--c" opacity="0.5">
            <ellipse cx="836" cy="212" rx="62" ry="17" />
            <ellipse cx="798" cy="204" rx="36" ry="13" />
          </g>
        </g>
      </g>

      <g className="login-scene__far">
        <path
          d="M0 306 C 132 268 260 262 384 288 C 508 314 628 306 742 278 C 812 260 862 264 900 274 L900 600 L0 600 Z"
          fill="url(#login-hill-far)"
        />
        <path
          d="M0 306 C 132 268 260 262 384 288 C 508 314 628 306 742 278 C 812 260 862 264 900 274"
          fill="none"
          stroke="#ffffff"
          strokeOpacity="0.2"
          strokeWidth="1.5"
        />
        <g>
          <rect x="258" y="292" width="4" height="16" rx="2" fill="#2d5f43" />
          <circle cx="260" cy="286" r="12" fill="#5fa878" />
          <circle cx="252" cy="292" r="8" fill="#4e9a6b" />
        </g>
      </g>

      <g className="login-scene__mid">
        <path
          d="M0 388 C 136 352 282 346 414 374 C 548 402 700 396 900 356 L900 600 L0 600 Z"
          fill="url(#login-hill-mid)"
        />
        <path
          d="M0 388 C 136 352 282 346 414 374 C 548 402 700 396 900 356"
          fill="none"
          stroke="#ffffff"
          strokeOpacity="0.14"
          strokeWidth="1.5"
        />
        <g transform="translate(520 352) scale(0.8)">
          <path
            d="M0 54 L0 16 Q 55 -28 110 16 L110 54 Z"
            fill="#ffffff"
            fillOpacity="0.3"
            stroke="#245c40"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <path
            d="M36 0 L36 54 M74 0 L74 54"
            stroke="#245c40"
            strokeWidth="1.2"
            opacity="0.5"
          />
          <rect x="-5" y="52" width="120" height="6" rx="3" fill="#245c40" opacity="0.8" />
        </g>
        <g>
          <rect x="718" y="338" width="6" height="20" fill="#2f6a4b" />
          <rect x="642" y="364" width="88" height="36" rx="3" fill="#f6faf0" />
          <path d="M634 366 L686 336 L738 366 Z" fill="#2f6a4b" />
          <rect x="656" y="374" width="12" height="12" rx="2" fill="#ffe6ae" />
          <rect x="704" y="374" width="12" height="12" rx="2" fill="#ffe6ae" />
          <rect x="676" y="382" width="14" height="18" rx="2" fill="#38795a" />
        </g>
        <g>
          <rect x="752" y="380" width="4" height="18" rx="2" fill="#2d5f43" />
          <circle cx="754" cy="372" r="16" fill="#4e9a6b" />
          <circle cx="744" cy="378" r="10" fill="#5fa878" />
          <circle cx="764" cy="378" r="10" fill="#488f63" />
        </g>
      </g>

      <g className="login-scene__near">
        <path
          d="M0 476 C 180 446 344 448 524 472 C 668 492 796 492 900 474 L900 600 L0 600 Z"
          fill="url(#login-hill-near)"
        />
        <g
          fill="none"
          stroke="#8fd3a4"
          strokeOpacity="0.22"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <path d="M-20 505 C 196 484 512 482 920 518" />
          <path d="M-20 532 C 214 510 546 508 920 544" />
          <path d="M-20 560 C 240 538 572 536 920 572" />
        </g>
      </g>
    </svg>
  );
}

function NightScene() {
  return (
    <svg
      className="login-scene"
      viewBox="0 0 900 600"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <filter id="login-moon-soft" x="-90%" y="-90%" width="280%" height="280%">
          <feGaussianBlur stdDeviation="30" />
        </filter>
        <linearGradient id="login-night-hill-far" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#386551" />
          <stop offset="100%" stopColor="#2b5645" />
        </linearGradient>
        <linearGradient id="login-night-hill-mid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#27503f" />
          <stop offset="100%" stopColor="#1e4334" />
        </linearGradient>
        <linearGradient id="login-night-hill-near" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1b4233" />
          <stop offset="100%" stopColor="#112f25" />
        </linearGradient>
        <filter id="login-night-blur" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>

      <g className="login-scene__sun">
        <circle cx="704" cy="118" r="70" fill="#dfe8de" opacity="0.3" filter="url(#login-moon-soft)" />
        <circle cx="704" cy="118" r="42" fill="#f0f1de" opacity="0.38" filter="url(#login-moon-soft)" />
        <circle cx="704" cy="118" r="27" fill="#f4f1dc" />
        <circle cx="696" cy="108" r="5" fill="#e6e2ca" opacity="0.55" />
        <circle cx="712" cy="126" r="3.6" fill="#e6e2ca" opacity="0.45" />
        <circle cx="710" cy="104" r="2.4" fill="#e6e2ca" opacity="0.4" />
      </g>

      <g className="login-scene__clouds">
        <g fill="#e9f3ee">
          <circle cx="96" cy="66" r="1.6" opacity="0.55" />
          <circle cx="182" cy="44" r="1.2" opacity="0.4" />
          <circle cx="300" cy="88" r="1.5" opacity="0.5" />
          <circle cx="416" cy="52" r="1.2" opacity="0.35" />
          <circle cx="520" cy="112" r="1.7" opacity="0.55" />
          <circle cx="612" cy="46" r="1.3" opacity="0.45" />
          <circle cx="764" cy="62" r="1.4" opacity="0.5" />
          <circle cx="842" cy="122" r="1.2" opacity="0.35" />
          <circle cx="858" cy="42" r="1.6" opacity="0.55" />
          <circle cx="480" cy="172" r="1.2" opacity="0.3" />
          <circle cx="248" cy="182" r="1.4" opacity="0.35" />
          <circle cx="122" cy="204" r="1.2" opacity="0.3" />
          <circle cx="680" cy="192" r="1.2" opacity="0.35" />
          <circle cx="352" cy="142" r="1.1" opacity="0.3" />
        </g>
        <g fill="#dce9e2" filter="url(#login-night-blur)">
          <g className="login-cloud login-cloud--a" opacity="0.14">
            <ellipse cx="228" cy="146" rx="92" ry="25" />
            <ellipse cx="284" cy="130" rx="54" ry="21" />
            <ellipse cx="172" cy="134" rx="42" ry="17" />
          </g>
          <g className="login-cloud login-cloud--b" opacity="0.1">
            <ellipse cx="600" cy="100" rx="68" ry="19" />
            <ellipse cx="648" cy="90" rx="40" ry="15" />
          </g>
        </g>
      </g>

      <g className="login-scene__far">
        <path
          d="M0 306 C 132 268 260 262 384 288 C 508 314 628 306 742 278 C 812 260 862 264 900 274 L900 600 L0 600 Z"
          fill="url(#login-night-hill-far)"
        />
        <path
          d="M0 306 C 132 268 260 262 384 288 C 508 314 628 306 742 278 C 812 260 862 264 900 274"
          fill="none"
          stroke="#d5e8dd"
          strokeOpacity="0.1"
          strokeWidth="1.5"
        />
        <g>
          <rect x="258" y="292" width="4" height="16" rx="2" fill="#17392c" />
          <circle cx="260" cy="286" r="12" fill="#35634f" />
          <circle cx="252" cy="292" r="8" fill="#2d5947" />
        </g>
      </g>

      <g className="login-scene__mid">
        <path
          d="M0 388 C 136 352 282 346 414 374 C 548 402 700 396 900 356 L900 600 L0 600 Z"
          fill="url(#login-night-hill-mid)"
        />
        <path
          d="M0 388 C 136 352 282 346 414 374 C 548 402 700 396 900 356"
          fill="none"
          stroke="#d5e8dd"
          strokeOpacity="0.07"
          strokeWidth="1.5"
        />
        <g transform="translate(520 352) scale(0.8)">
          <path
            d="M0 54 L0 16 Q 55 -28 110 16 L110 54 Z"
            fill="#dfeee7"
            fillOpacity="0.1"
            stroke="#6f9c84"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <path
            d="M36 0 L36 54 M74 0 L74 54"
            stroke="#6f9c84"
            strokeWidth="1.2"
            opacity="0.45"
          />
          <rect x="-5" y="52" width="120" height="6" rx="3" fill="#123527" opacity="0.85" />
        </g>
        <g>
          <circle cx="662" cy="380" r="16" fill="#ffc978" opacity="0.2" filter="url(#login-night-blur)" />
          <circle cx="710" cy="380" r="16" fill="#ffc978" opacity="0.2" filter="url(#login-night-blur)" />
          <rect x="718" y="338" width="6" height="20" fill="#123527" />
          <rect x="642" y="364" width="88" height="36" rx="3" fill="#dde6da" />
          <path d="M634 366 L686 336 L738 366 Z" fill="#123527" />
          <rect x="656" y="374" width="12" height="12" rx="2" fill="#ffcf87" />
          <rect x="704" y="374" width="12" height="12" rx="2" fill="#ffcf87" />
          <rect x="676" y="382" width="14" height="18" rx="2" fill="#1c4636" />
        </g>
        <g>
          <rect x="752" y="380" width="4" height="18" rx="2" fill="#17392c" />
          <circle cx="754" cy="372" r="16" fill="#2f5f49" />
          <circle cx="744" cy="378" r="10" fill="#386a51" />
          <circle cx="764" cy="378" r="10" fill="#2a5642" />
        </g>
      </g>

      <g className="login-scene__near">
        <path
          d="M0 476 C 180 446 344 448 524 472 C 668 492 796 492 900 474 L900 600 L0 600 Z"
          fill="url(#login-night-hill-near)"
        />
        <g
          fill="none"
          stroke="#8fc7a4"
          strokeOpacity="0.14"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <path d="M-20 505 C 196 484 512 482 920 518" />
          <path d="M-20 532 C 214 510 546 508 920 544" />
          <path d="M-20 560 C 240 538 572 536 920 572" />
        </g>
        <g fill="#d7eb9b">
          <circle cx="512" cy="504" r="2" opacity="0.5" />
          <circle cx="588" cy="526" r="1.6" opacity="0.4" />
          <circle cx="702" cy="516" r="1.8" opacity="0.45" />
          <circle cx="824" cy="508" r="1.4" opacity="0.35" />
          <circle cx="440" cy="540" r="1.5" opacity="0.35" />
        </g>
      </g>
    </svg>
  );
}

export default function LoginScene({ theme }: { theme: LoginTheme }) {
  return theme === 'dark' ? <NightScene /> : <DayScene />;
}
