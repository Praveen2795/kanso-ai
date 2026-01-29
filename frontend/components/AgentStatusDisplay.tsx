import React, { useMemo } from 'react';
import { AgentStatus, AgentType } from '../types';

interface Props {
  status: AgentStatus;
}

const AgentStatusDisplay: React.FC<Props> = ({ status }) => {
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

  // Clean SVG Icons
  const icons = {
    analyst: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
    ),
    architect: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
        <path d="M3 21h18M9 8h1M9 12h1M9 16h1M14 8h1M14 12h1M14 16h1M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
      </svg>
    ),
    estimator: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
    reviewer: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    ),
    web: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
  };

  const getNodeStyle = (type: AgentType) => {
    const isActive = layoutState.activeNode === type || (type === AgentType.WEB_SEARCH && layoutState.isWebSearching);
    
    const colors: Record<string, { border: string; glow: string; text: string; bg: string }> = {
      [AgentType.WEB_SEARCH]: { border: 'border-teal-400', glow: 'shadow-teal-400/30', text: 'text-teal-400', bg: 'bg-teal-400/10' },
      [AgentType.ANALYST]: { border: 'border-sky-400', glow: 'shadow-sky-400/30', text: 'text-sky-400', bg: 'bg-sky-400/10' },
      [AgentType.ARCHITECT]: { border: 'border-violet-400', glow: 'shadow-violet-400/30', text: 'text-violet-400', bg: 'bg-violet-400/10' },
      [AgentType.ESTIMATOR]: { border: 'border-amber-400', glow: 'shadow-amber-400/30', text: 'text-amber-400', bg: 'bg-amber-400/10' },
      [AgentType.REVIEWER]: { border: 'border-rose-400', glow: 'shadow-rose-400/30', text: 'text-rose-400', bg: 'bg-rose-400/10' },
    };

    const c = colors[type] || colors[AgentType.ANALYST];
    
    return {
      container: isActive 
        ? `${c.border} ${c.bg} shadow-lg ${c.glow}` 
        : 'border-slate-700/50 bg-slate-800/30',
      text: isActive ? c.text : 'text-slate-500',
      icon: isActive ? c.text : 'text-slate-600',
      pulse: isActive ? 'animate-pulse' : '',
    };
  };

  const renderNode = (type: AgentType, label: string, icon: React.ReactNode, isMain = true) => {
    const style = getNodeStyle(type);
    
    return (
      <div className={`
        relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 
        transition-all duration-500 ease-out backdrop-blur-sm
        ${isMain ? 'min-w-[100px]' : 'min-w-[80px]'}
        ${style.container}
        ${style.pulse}
      `}>
        <div className={`transition-colors duration-500 ${style.icon}`}>
          {icon}
        </div>
        <span className={`text-[10px] font-semibold uppercase tracking-wider transition-colors duration-500 ${style.text}`}>
          {label}
        </span>
      </div>
    );
  };

  const renderConnector = (active: boolean, color: string = 'bg-slate-700') => (
    <div className="flex items-center gap-1 mx-2">
      {[...Array(3)].map((_, i) => (
        <div 
          key={i}
          className={`w-2 h-0.5 rounded-full transition-all duration-300 ${
            active ? `${color} animate-pulse` : 'bg-slate-700/50'
          }`}
          style={{ animationDelay: `${i * 100}ms` }}
        />
      ))}
      <svg className={`w-3 h-3 ${active ? color.replace('bg-', 'text-') : 'text-slate-700/50'}`} viewBox="0 0 12 12">
        <path d="M2 6h8M7 3l3 3-3 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
  );

  const isAnalystActive = layoutState.activeNode === AgentType.ANALYST;
  const isArchitectActive = layoutState.activeNode === AgentType.ARCHITECT;
  const isEstimatorActive = layoutState.activeNode === AgentType.ESTIMATOR;
  const isReviewerActive = layoutState.activeNode === AgentType.REVIEWER;

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col items-center justify-center p-8 animate-in fade-in duration-700">
      
      {/* Main Pipeline */}
      <div className="relative w-full">
        
        {/* Web Search - Above Architect */}
        {layoutState.isWebSearching && (
          <div className="absolute left-1/2 -translate-x-1/2 -top-24 flex flex-col items-center animate-in fade-in slide-in-from-top-4 duration-500">
            {renderNode(AgentType.WEB_SEARCH, 'Web Search', icons.web, false)}
            <div className="h-6 w-0.5 bg-gradient-to-b from-teal-400 to-transparent animate-pulse" />
          </div>
        )}

        {/* Main Agent Row */}
        <div className="flex items-center justify-center gap-0">
          {renderNode(AgentType.ANALYST, 'Analyst', icons.analyst)}
          {renderConnector(isAnalystActive || isArchitectActive, 'bg-sky-400')}
          {renderNode(AgentType.ARCHITECT, 'Architect', icons.architect)}
          {renderConnector(isArchitectActive || isEstimatorActive, 'bg-violet-400')}
          {renderNode(AgentType.ESTIMATOR, 'Estimator', icons.estimator)}
        </div>

        {/* Reviewer - Below with validation loop */}
        <div className="flex justify-center mt-6">
          <div className="relative">
            {/* Loop indicators */}
            {(layoutState.connectionType === 'architect-reviewer' || layoutState.connectionType === 'estimator-reviewer') && (
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 flex items-center gap-1">
                <svg className="w-4 h-4 text-rose-400 animate-spin" style={{ animationDuration: '2s' }} viewBox="0 0 24 24">
                  <path fill="none" stroke="currentColor" strokeWidth="2" d="M12 2v4m0 12v4M2 12h4m12 0h4"/>
                </svg>
                <span className="text-[9px] text-rose-400 font-medium uppercase tracking-wider">Validating</span>
              </div>
            )}
            
            {/* Connection line */}
            <div className={`absolute -top-6 left-1/2 -translate-x-1/2 w-0.5 h-6 transition-colors duration-300 ${
              isReviewerActive || layoutState.connectionType ? 'bg-gradient-to-b from-slate-600 to-rose-400' : 'bg-slate-700/30'
            }`} />
            
            {renderNode(AgentType.REVIEWER, 'Reviewer', icons.reviewer)}
          </div>
        </div>

        {/* Feedback Loop Visual */}
        {layoutState.isFeedback && (
          <div className="absolute left-1/2 -translate-x-1/2 top-1/2 -translate-y-1/2 pointer-events-none">
            <div className="w-32 h-32 border-2 border-dashed border-rose-400/30 rounded-full animate-[spin_8s_linear_infinite]" />
          </div>
        )}
      </div>

      {/* Status Text */}
      <div className="text-center mt-10 space-y-3">
        <div className="flex items-center justify-center gap-2">
          {(layoutState.isWebSearching || layoutState.isFeedback) && (
            <span className={`inline-flex w-2 h-2 rounded-full ${
              layoutState.isFeedback ? 'bg-rose-400' : 'bg-teal-400'
            } animate-ping`} />
          )}
          <h3 className={`text-lg font-semibold tracking-tight transition-colors duration-500 ${
            layoutState.isFeedback 
              ? 'text-rose-400' 
              : layoutState.isWebSearching 
                ? 'text-teal-400' 
                : 'text-slate-200'
          }`}>
            {layoutState.isWebSearching 
              ? 'External Search Active' 
              : layoutState.isFeedback 
                ? 'Revising Based on Feedback' 
                : `${status.name} Agent Working`}
          </h3>
        </div>
        <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
          {status.message}
        </p>
      </div>

      {/* Progress dots */}
      <div className="mt-8 flex items-center gap-2">
        {[AgentType.ANALYST, AgentType.ARCHITECT, AgentType.ESTIMATOR, AgentType.REVIEWER].map((type, i) => {
          const isPast = [AgentType.ANALYST, AgentType.ARCHITECT, AgentType.ESTIMATOR, AgentType.REVIEWER]
            .indexOf(layoutState.activeNode as AgentType) > i;
          const isCurrent = layoutState.activeNode === type;
          
          return (
            <React.Fragment key={type}>
              <div className={`w-2 h-2 rounded-full transition-all duration-500 ${
                isCurrent 
                  ? 'bg-white scale-125 shadow-lg shadow-white/50' 
                  : isPast 
                    ? 'bg-slate-400' 
                    : 'bg-slate-700'
              }`} />
              {i < 3 && <div className={`w-8 h-0.5 transition-colors duration-500 ${
                isPast ? 'bg-slate-400' : 'bg-slate-700'
              }`} />}
            </React.Fragment>
          );
        })}
      </div>

    </div>
  );
};

export default AgentStatusDisplay;