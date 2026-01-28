import React, { useMemo } from 'react';

const ImpactBackground: React.FC = () => {
  // 1. Chaos Elements (Left Side) - Floating towards center
  // Memoized to prevent regeneration on re-renders (like typing)
  const chaosItems = useMemo(() => Array.from({ length: 25 }).map((_, i) => ({
    id: i,
    top: Math.random() * 90 + 5, // %
    delay: Math.random() * 5, // s
    duration: 12 + Math.random() * 10, // s
    type: i % 4 === 0 ? '?' : i % 3 === 0 ? '○' : '•',
    size: Math.random() * 1.5 + 1, // rem
    color: i % 2 === 0 ? '#22d3ee' : '#818cf8', // Cyan / Indigo
    initialLeft: Math.random() * -10 // Stagger start positions slightly
  })), []);

  // 2. Structured Elements (Right Side) - Gantt Bars emerging
  // Memoized to prevent regeneration on re-renders
  const orderItems = useMemo(() => Array.from({ length: 15 }).map((_, i) => ({
    id: i,
    top: 20 + (i * 5), // %
    width: 10 + Math.random() * 30, // %
    delay: Math.random() * 3, // s
    duration: 5 + Math.random() * 5, // s
    color: i % 2 === 0 ? 'bg-orange-400' : 'bg-cyan-400' 
  })), []);

  return (
    // z-0 ensures it sits ON TOP of the root background but BEHIND content
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 bg-[#0B1021]">
      <style>{`
        @keyframes floatIn {
          0% { transform: translateX(-50px) rotate(0deg); opacity: 0; }
          10% { opacity: 1; } 
          70% { opacity: 0.8; } 
          /* Fade out and stop BEFORE reaching the center (35vw instead of 50vw) */
          100% { transform: translateX(35vw) rotate(180deg); opacity: 0; }
        }
        @keyframes slideForm {
          0% { transform: translateX(0) scaleX(0); opacity: 0; }
          10% { transform: translateX(20px) scaleX(1); opacity: 1; }
          70% { opacity: 0.8; }
          100% { transform: translateX(150px) scaleX(1); opacity: 0; }
        }
      `}</style>

      {/* Background Gradient Mesh */}
      <div className="absolute inset-0 opacity-50 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-indigo-900/40 via-[#0B1021] to-[#0B1021]"></div>
      
      {/* Connecting Arc - made subtler */}
      <svg className="absolute inset-0 w-full h-full opacity-30" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="arcGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0" />
            <stop offset="45%" stopColor="#6366f1" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#fb923c" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M 0 90 Q 50 30 100 90" stroke="url(#arcGradient)" strokeWidth="0.5" fill="none" />
      </svg>

      {/* Left Side: Chaos (Drifting In) */}
      <div className="absolute inset-y-0 left-0 w-1/2 overflow-hidden">
        {chaosItems.map((item) => (
          <div
            key={item.id}
            className="absolute font-sans font-light select-none flex items-center justify-center"
            style={{
              color: item.color,
              left: `${item.initialLeft}px`,
              top: `${item.top}%`,
              fontSize: `${item.size}rem`,
              textShadow: `0 0 15px ${item.color}`, 
              animation: `floatIn ${item.duration}s linear infinite`,
              animationDelay: `${item.delay}s`,
              opacity: 0 // handled by keyframe
            }}
          >
            {item.type}
          </div>
        ))}
      </div>

      {/* Right Side: Order (Emerging Out) */}
      <div className="absolute inset-y-0 right-0 w-1/2 overflow-hidden">
         <div className="relative w-full h-full">
            {orderItems.map((bar) => (
              <div
                key={bar.id}
                className={`absolute h-2 rounded-full ${bar.color}`}
                style={{
                  top: `${bar.top}%`,
                  // Moved significantly further to the right (55% of the right-half container)
                  // This ensures they are very far from the center text box
                  left: '55%', 
                  width: `${bar.width}%`,
                  animation: `slideForm ${bar.duration}s ease-out infinite`,
                  animationDelay: `${bar.delay}s`,
                  opacity: 0, // handled by keyframe
                  boxShadow: `0 0 12px ${bar.color.includes('orange') ? 'rgba(251,146,60,0.6)' : 'rgba(34,211,238,0.6)'}`
                }}
              />
            ))}
         </div>
      </div>

      {/* Vignette Overlay */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#0f172a_100%)] opacity-60"></div>
    </div>
  );
};

// Also wrap the component in memo to prevent unnecessary re-renders from parent updates if props (none here) don't change
export default React.memo(ImpactBackground);