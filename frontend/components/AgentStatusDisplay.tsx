import React, { useMemo } from 'react';
import { AgentStatus, AgentType } from '../types';

interface Props {
  status: AgentStatus;
}

const AgentStatusDisplay: React.FC<Props> = ({ status }) => {
  const layoutState = useMemo(() => {
    const msg = status.message.toLowerCase();
    const name = status.name;

    // Check if this is the Manager agent (chat refinement mode)
    const isManagerMode = name === AgentType.MANAGER;
    
    // Check for research activity
    const isResearching = msg.includes("researching") || 
                          msg.includes("url") || 
                          msg.includes("term research") ||
                          name === AgentType.RESEARCHER;

    // Check for validation/feedback loops
    const isValidating = msg.includes("validating") || 
                         msg.includes("validation") ||
                         name === AgentType.REVIEWER;
    
    const isFeedback = msg.includes("feedback") || 
                       msg.includes("retrying") || 
                       msg.includes("improvement") ||
                       msg.includes("re-designing") ||
                       msg.includes("recalculating");

    // Extract iteration info if present
    const iterationMatch = msg.match(/iteration (\d+)\/(\d+)/);
    const iteration = iterationMatch ? {
      current: parseInt(iterationMatch[1]),
      total: parseInt(iterationMatch[2])
    } : null;

    return { 
      activeNode: name, 
      isManagerMode, 
      isResearching, 
      isValidating,
      isFeedback,
      iteration
    };
  }, [status]);

  // Get color theme for each agent type
  const getAgentTheme = (type: AgentType) => {
    const themes: Record<string, { primary: string; bg: string; border: string; glow: string }> = {
      [AgentType.RESEARCHER]: { primary: 'text-teal-400', bg: 'bg-teal-400/10', border: 'border-teal-400/50', glow: 'shadow-teal-400/20' },
      [AgentType.ANALYST]: { primary: 'text-sky-400', bg: 'bg-sky-400/10', border: 'border-sky-400/50', glow: 'shadow-sky-400/20' },
      [AgentType.ARCHITECT]: { primary: 'text-violet-400', bg: 'bg-violet-400/10', border: 'border-violet-400/50', glow: 'shadow-violet-400/20' },
      [AgentType.ESTIMATOR]: { primary: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/50', glow: 'shadow-amber-400/20' },
      [AgentType.REVIEWER]: { primary: 'text-rose-400', bg: 'bg-rose-400/10', border: 'border-rose-400/50', glow: 'shadow-rose-400/20' },
      [AgentType.MANAGER]: { primary: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/50', glow: 'shadow-emerald-400/20' },
    };
    return themes[type] || themes[AgentType.ANALYST];
  };

  const theme = getAgentTheme(status.name);

  // Icons for each agent (larger for focus display)
  const getIcon = (type: AgentType) => {
    const iconClass = "w-12 h-12";
    switch (type) {
      case AgentType.ANALYST:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass}>
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        );
      case AgentType.RESEARCHER:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass}>
            <circle cx="12" cy="12" r="10" />
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
        );
      case AgentType.ARCHITECT:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass}>
            <path d="M3 21h18M9 8h1M9 12h1M9 16h1M14 8h1M14 12h1M14 16h1M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
          </svg>
        );
      case AgentType.ESTIMATOR:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass}>
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        );
      case AgentType.REVIEWER:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass}>
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
        );
      case AgentType.MANAGER:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass}>
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        );
      default:
        return null;
    }
  };

  // Get friendly status title
  const getStatusTitle = () => {
    if (layoutState.isFeedback) return 'Revising Based on Feedback';
    if (layoutState.isValidating) return 'Validating Output';
    if (layoutState.isResearching) return 'Researching Context';
    
    // Agent-specific titles
    switch (status.name) {
      case AgentType.ANALYST: return 'Analyzing Requirements';
      case AgentType.ARCHITECT: return 'Designing Structure';
      case AgentType.ESTIMATOR: return 'Estimating Duration';
      case AgentType.REVIEWER: return 'Reviewing Quality';
      case AgentType.MANAGER: return 'Processing Request';
      default: return `${status.name} Working`;
    }
  };

  // Define pipeline steps for progress indicator
  const pipelineSteps = [
    AgentType.ANALYST,
    AgentType.ARCHITECT,
    AgentType.ESTIMATOR,
    AgentType.REVIEWER,
  ];
  
  const currentStepIndex = pipelineSteps.indexOf(status.name);

  // Unified single-agent focused display
  return (
    <div className="w-full max-w-md mx-auto flex flex-col items-center justify-center py-12 px-6 animate-in fade-in duration-500">
      
      {/* Compact Pipeline Progress (only for non-Manager) */}
      {!layoutState.isManagerMode && (
        <div className="mb-8 flex items-center gap-2">
          {pipelineSteps.map((step, i) => {
            const isPast = currentStepIndex > i;
            const isCurrent = currentStepIndex === i;
            const stepTheme = getAgentTheme(step);
            
            return (
              <React.Fragment key={step}>
                <div 
                  className={`
                    flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold
                    transition-all duration-300
                    ${isCurrent 
                      ? `${stepTheme.bg} ${stepTheme.border} border-2 ${stepTheme.primary} scale-110` 
                      : isPast 
                        ? 'bg-slate-700 text-slate-400 border border-slate-600' 
                        : 'bg-slate-800/50 text-slate-600 border border-slate-700/50'
                    }
                  `}
                  title={step}
                >
                  {i + 1}
                </div>
                {i < pipelineSteps.length - 1 && (
                  <div className={`w-6 h-0.5 transition-colors duration-300 ${
                    isPast ? 'bg-slate-600' : 'bg-slate-800'
                  }`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      {/* Main Agent Card */}
      <div className="relative">
        {/* Outer glow effect */}
        <div className={`absolute inset-0 -m-6 rounded-3xl ${theme.bg} blur-xl opacity-60`} />
        
        {/* Animated pulse ring */}
        <div className={`absolute inset-0 -m-4 rounded-2xl ${theme.border} border animate-pulse`} />
        
        {/* Agent Card */}
        <div className={`
          relative flex flex-col items-center gap-4 p-10 rounded-xl 
          ${theme.border} border
          ${theme.bg} backdrop-blur-sm
          shadow-2xl ${theme.glow}
          transition-all duration-500
        `}>
          {/* Icon with subtle animation */}
          <div className={`${theme.primary} transition-transform duration-1000`}>
            {getIcon(status.name)}
          </div>
          
          {/* Agent Name */}
          <span className={`text-sm font-bold uppercase tracking-[0.2em] ${theme.primary}`}>
            {status.name}
          </span>
          
          {/* Iteration Badge (if in validation loop) */}
          {layoutState.iteration && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/70 border border-slate-700">
              <div className="flex gap-1">
                {[...Array(layoutState.iteration.total)].map((_, i) => (
                  <div 
                    key={i}
                    className={`w-2 h-2 rounded-full transition-colors ${
                      i < layoutState.iteration!.current 
                        ? theme.primary.replace('text-', 'bg-')
                        : 'bg-slate-600'
                    }`}
                  />
                ))}
              </div>
              <span className="text-xs text-slate-400">
                Pass {layoutState.iteration.current}/{layoutState.iteration.total}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Status Section */}
      <div className="text-center mt-10 space-y-3 max-w-sm">
        {/* Status Title */}
        <div className="flex items-center justify-center gap-3">
          {/* Pulsing indicator */}
          <span className={`
            inline-flex w-2.5 h-2.5 rounded-full 
            ${theme.primary.replace('text-', 'bg-')} 
            animate-pulse
          `} />
          
          <h3 className={`text-lg font-semibold tracking-tight ${theme.primary}`}>
            {getStatusTitle()}
          </h3>
        </div>
        
        {/* Status Message */}
        <p className="text-slate-400 text-sm leading-relaxed">
          {status.message}
        </p>
      </div>

      {/* Subtle Loading Animation */}
      <div className="mt-10 flex items-center justify-center gap-1.5">
        {[...Array(4)].map((_, i) => (
          <div 
            key={i}
            className={`
              w-1.5 h-1.5 rounded-full 
              ${theme.primary.replace('text-', 'bg-')}/50 
              animate-bounce
            `}
            style={{ animationDelay: `${i * 100}ms`, animationDuration: '0.8s' }}
          />
        ))}
      </div>

    </div>
  );
};

export default AgentStatusDisplay;