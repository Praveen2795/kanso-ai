import React from 'react';
import { AgentStatus, AgentType } from '../types';

interface Props {
  status: AgentStatus;
}

const AgentStatusDisplay: React.FC<Props> = ({ status }) => {
  if (!status.active) return null;

  const getAgentColor = (type: AgentType) => {
    switch (type) {
      case AgentType.ANALYST: return 'text-blue-400 border-blue-400';
      case AgentType.ARCHITECT: return 'text-purple-400 border-purple-400';
      case AgentType.ESTIMATOR: return 'text-yellow-400 border-yellow-400';
      case AgentType.REVIEWER: return 'text-red-400 border-red-400';
      default: return 'text-gray-400 border-gray-400';
    }
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 space-y-4 animate-in fade-in zoom-in duration-300">
      <div className={`relative w-24 h-24 rounded-full border-4 flex items-center justify-center ${getAgentColor(status.name)} animate-pulse-fast`}>
        <div className="text-4xl">
           {status.name === AgentType.ANALYST && "🔍"}
           {status.name === AgentType.ARCHITECT && "📐"}
           {status.name === AgentType.ESTIMATOR && "⏱️"}
           {status.name === AgentType.REVIEWER && "🛡️"}
        </div>
        {/* Orbiting particles */}
        <div className="absolute top-0 left-0 w-full h-full animate-spin duration-[3000ms]">
          <div className="w-3 h-3 bg-white rounded-full absolute -top-1 left-1/2 shadow-[0_0_10px_rgba(255,255,255,0.8)]"></div>
        </div>
      </div>
      
      <div className="text-center space-y-1">
        <h3 className={`text-xl font-bold tracking-widest uppercase ${getAgentColor(status.name).split(' ')[0]}`}>
          {status.name} Agent
        </h3>
        <p className="text-slate-400 text-sm max-w-md animate-pulse">
          {status.message}
        </p>
      </div>
    </div>
  );
};

export default AgentStatusDisplay;