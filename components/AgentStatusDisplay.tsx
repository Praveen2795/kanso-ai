import React, { useMemo } from 'react';
import { AgentStatus, AgentType } from '../types';

interface Props {
  status: AgentStatus;
}

const AgentStatusDisplay: React.FC<Props> = ({ status }) => {
  // Determine active state and feedback loops based on messages
  const layoutState = useMemo(() => {
    const msg = status.message.toLowerCase();
    const name = status.name;

    let activeNode = name;
    let isFeedback = false;
    let connectionType: 'architect-reviewer' | 'estimator-reviewer' | 'forward' | null = null;
    
    const isWebSearching = msg.includes("researching") || 
                           msg.includes("verifying") || 
                           msg.includes("searching") || 
                           msg.includes("google") || 
                           msg.includes("url") || 
                           name === AgentType.WEB_SEARCH;

    // Detect Validation Loops
    if (name === AgentType.REVIEWER) {
        if (msg.includes("structure") || msg.includes("dependencies") || msg.includes("architect")) {
            connectionType = 'architect-reviewer';
        } else if (msg.includes("time") || msg.includes("estimates") || msg.includes("buffer")) {
            connectionType = 'estimator-reviewer';
        }
    } else if (name === AgentType.ARCHITECT && (msg.includes("feedback") || msg.includes("re-designing"))) {
         connectionType = 'architect-reviewer';
         isFeedback = true;
    } else if (name === AgentType.ESTIMATOR && (msg.includes("feedback") || msg.includes("recalculating"))) {
         connectionType = 'estimator-reviewer';
         isFeedback = true;
    }

    if (name === AgentType.MANAGER) {
        activeNode = AgentType.MANAGER;
    }

    return { activeNode, isFeedback, isWebSearching, connectionType };
  }, [status]);

  // Node Coordinates (Percentage 0-100)
  const pos = {
    web: { x: 50, y: 15 },
    analyst: { x: 20, y: 50 },
    architect: { x: 50, y: 50 },
    estimator: { x: 80, y: 50 },
    reviewer: { x: 50, y: 85 }
  };

  const renderNode = (type: AgentType, label: string, icon: string, x: number, y: number) => {
    const isWeb = type === AgentType.WEB_SEARCH;
    const isActive = layoutState.activeNode === type || (isWeb && layoutState.isWebSearching);
    
    // Style logic
    let borderColor = 'border-slate-700';
    let glow = '';
    let textColor = 'text-slate-500';
    let iconColor = 'grayscale opacity-50';
    let animation = '';
    let bgColor = 'bg-slate-900/90';
    
    if (isActive) {
        iconColor = 'grayscale-0 opacity-100';
        animation = 'animate-pulse';
        switch (type) {
            case AgentType.WEB_SEARCH:
                borderColor = 'border-emerald-500';
                glow = 'shadow-[0_0_20px_rgba(16,185,129,0.3)]';
                textColor = 'text-emerald-400';
                break;
            case AgentType.ANALYST:
                borderColor = 'border-blue-500';
                glow = 'shadow-[0_0_20px_rgba(59,130,246,0.3)]';
                textColor = 'text-blue-400';
                break;
            case AgentType.ARCHITECT:
                borderColor = 'border-indigo-500';
                glow = 'shadow-[0_0_20px_rgba(99,102,241,0.3)]';
                textColor = 'text-indigo-400';
                break;
            case AgentType.ESTIMATOR:
                borderColor = 'border-amber-500';
                glow = 'shadow-[0_0_20px_rgba(245,158,11,0.3)]';
                textColor = 'text-amber-400';
                break;
            case AgentType.REVIEWER:
                borderColor = 'border-rose-500';
                glow = 'shadow-[0_0_20px_rgba(244,63,94,0.3)]';
                textColor = 'text-rose-400';
                break;
        }
    }

    const shapeClass = isWeb 
        ? `w-20 h-20 rounded-full` 
        : `w-28 h-14 rounded-lg`;

    return (
        <div 
            className={`absolute transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center justify-center transition-all duration-500 z-10 ${bgColor} border-2 ${shapeClass} ${borderColor} ${glow} ${animation}`}
            style={{ left: `${x}%`, top: `${y}%` }}
        >
            <div className={`text-2xl mb-1 transition-all duration-500 ${iconColor}`}>{icon}</div>
            <span className={`text-[9px] font-bold uppercase tracking-widest text-center transition-colors duration-500 ${textColor}`}>
                {label}
            </span>
        </div>
    );
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col items-center justify-center p-6 animate-in fade-in zoom-in duration-500">
      
      {/* CHART CONTAINER */}
      <div className="relative w-full aspect-[2/1.2] max-h-[400px] mb-6 select-none">
        
        {/* SVG CONNECTIONS LAYER */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-0" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
            
            {/* --- STATIC PATHS --- */}
            {/* Clean, simple lines without arrowheads */}

            {/* 1. Web -> Analyst (Curve Top-Left) */}
            <path d="M 46 18 Q 20 18 20 42" fill="none" stroke="#334155" strokeWidth="1" />
            
            {/* 2. Web -> Architect (Straight Down) */}
            <path d="M 50 22 L 50 42" fill="none" stroke="#334155" strokeWidth="1" />

            {/* 3. Analyst -> Architect (Horizontal) */}
            <path d="M 28 50 L 42 50" fill="none" stroke="#334155" strokeWidth="1" />

            {/* 4. Architect -> Estimator (Horizontal) */}
            <path d="M 58 50 L 72 50" fill="none" stroke="#334155" strokeWidth="1" />

            {/* 5. Architect <-> Reviewer (Vertical Loop) */}
            {/* Down */}
            <path d="M 48 58 L 48 77" fill="none" stroke="#334155" strokeWidth="1" />
            {/* Up */}
            <path d="M 52 77 L 52 58" fill="none" stroke="#334155" strokeWidth="1" />
            
            {/* 6. Estimator <-> Reviewer (Curved Loop) */}
            {/* Est -> Rev */}
            <path d="M 80 58 Q 80 85 58 85" fill="none" stroke="#334155" strokeWidth="1" />
            {/* Rev -> Est */}
            <path d="M 58 82 Q 76 82 76 58" fill="none" stroke="#334155" strokeWidth="1" />


            {/* --- ACTIVE ANIMATIONS --- */}

            {/* Web Active */}
            {layoutState.isWebSearching && (
                <>
                  <path d="M 46 18 Q 20 18 20 42" fill="none" stroke="#10b981" strokeWidth="1.5" strokeDasharray="4" className="animate-[dash_1s_linear_infinite]" />
                  <path d="M 50 22 L 50 42" fill="none" stroke="#10b981" strokeWidth="1.5" strokeDasharray="4" className="animate-[dash_1s_linear_infinite]" />
                </>
            )}

            {/* Architect -> Estimator Active (Estimator working) */}
            {layoutState.activeNode === AgentType.ESTIMATOR && !layoutState.isFeedback && (
                 <path d="M 58 50 L 72 50" fill="none" stroke="#f59e0b" strokeWidth="1.5" />
            )}

            {/* Analyst -> Architect Active (Architect working initially) */}
            {layoutState.activeNode === AgentType.ARCHITECT && !layoutState.isFeedback && (
                 <path d="M 28 50 L 42 50" fill="none" stroke="#6366f1" strokeWidth="1.5" />
            )}

            {/* Validation Loops */}
            {layoutState.connectionType === 'architect-reviewer' && (
                <>
                    <path d="M 48 58 L 48 77" fill="none" stroke="#fb7185" strokeWidth="1.5" />
                    <path d="M 52 77 L 52 58" fill="none" stroke="#fb7185" strokeWidth="1.5" />
                </>
            )}

            {layoutState.connectionType === 'estimator-reviewer' && (
                <>
                    <path d="M 80 58 Q 80 85 58 85" fill="none" stroke="#fb7185" strokeWidth="1.5" />
                    <path d="M 58 82 Q 76 82 76 58" fill="none" stroke="#fb7185" strokeWidth="1.5" />
                </>
            )}

        </svg>

        {/* NODES */}
        {renderNode(AgentType.WEB_SEARCH, 'Web Search', '🌐', pos.web.x, pos.web.y)}
        {renderNode(AgentType.ANALYST, 'Analyst', '🔍', pos.analyst.x, pos.analyst.y)}
        {renderNode(AgentType.ARCHITECT, 'Architect', '📐', pos.architect.x, pos.architect.y)}
        {renderNode(AgentType.ESTIMATOR, 'Estimator', '⏱️', pos.estimator.x, pos.estimator.y)}
        {renderNode(AgentType.REVIEWER, 'Reviewer', '🛡️', pos.reviewer.x, pos.reviewer.y)}

      </div>

      {/* STATUS TEXT */}
      <div className="text-center space-y-2 h-16">
        <h3 className={`text-xl font-bold tracking-tight transition-colors duration-500
            ${layoutState.isFeedback ? 'text-rose-400' : layoutState.isWebSearching ? 'text-emerald-400' : 'text-slate-200'}
        `}>
          {layoutState.isWebSearching ? 'External Search Active' : layoutState.isFeedback ? 'Revising Plan' : `${status.name} Agent Working`}
        </h3>
        <p className="text-slate-400 text-sm max-w-xl mx-auto leading-relaxed animate-in fade-in slide-in-from-bottom-2">
          {status.message}
        </p>
      </div>

      <style>{`
        @keyframes dash {
          to {
            stroke-dashoffset: -20;
          }
        }
      `}</style>

    </div>
  );
};

export default AgentStatusDisplay;