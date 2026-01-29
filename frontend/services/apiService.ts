/**
 * API Service for communicating with Kanso.AI backend
 */

import { 
  ProjectData, 
  Task, 
  AgentStatus, 
  AgentType, 
  UploadedFile 
} from '../types';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

// Generate unique client ID for WebSocket
const generateClientId = () => `kanso_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// --- Types for API requests/responses ---

interface AnalysisResponse {
  needsClarification: boolean;
  questions: string[];
  reasoning: string;
}

interface PlanGenerationResult {
  project: ProjectData;
  success: boolean;
  error?: string;
}

interface ChatResponse {
  reply: string;
  updatedPlan?: ProjectData;
}

interface ChatMessage {
  role: string;
  content: string;
}

// --- REST API Functions ---

/**
 * Analyze a project request to determine if clarification is needed
 */
export const analyzeRequest = async (
  topic: string, 
  chatHistory: string[] = []
): Promise<AnalysisResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, chatHistory })
  });
  
  if (!response.ok) {
    throw new Error(`Analysis failed: ${response.statusText}`);
  }
  
  return response.json();
};

/**
 * Generate a complete project plan (without real-time status)
 */
export const generatePlan = async (
  topic: string,
  context: string,
  file?: UploadedFile
): Promise<PlanGenerationResult> => {
  const response = await fetch(`${API_BASE_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, context, file })
  });
  
  if (!response.ok) {
    throw new Error(`Plan generation failed: ${response.statusText}`);
  }
  
  return response.json();
};

/**
 * Chat with the project manager to refine the plan
 */
export const chatWithManager = async (
  project: ProjectData,
  message: string,
  history: ChatMessage[]
): Promise<ChatResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project, message, history })
  });
  
  if (!response.ok) {
    throw new Error(`Chat failed: ${response.statusText}`);
  }
  
  return response.json();
};

// --- WebSocket Service for Real-time Updates ---

type StatusCallback = (status: AgentStatus) => void;
type MessageCallback = (type: string, data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private clientId: string;
  private statusCallbacks: StatusCallback[] = [];
  private messageCallbacks: MessageCallback[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  
  constructor() {
    this.clientId = generateClientId();
  }
  
  /**
   * Connect to the WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }
      
      this.ws = new WebSocket(`${WS_BASE_URL}/ws/${this.clientId}`);
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        resolve();
      };
      
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Handle status updates
          if (data.active !== undefined && data.agent !== undefined) {
            const status: AgentStatus = {
              active: data.active,
              name: data.agent as AgentType,
              message: data.message || ''
            };
            this.statusCallbacks.forEach(cb => cb(status));
          } else {
            // Handle other message types
            this.messageCallbacks.forEach(cb => cb(data.type, data.data || data));
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
      
      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.attemptReconnect();
      };
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
    });
  }
  
  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      setTimeout(() => this.connect(), this.reconnectDelay * this.reconnectAttempts);
    }
  }
  
  /**
   * Disconnect from the WebSocket server
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
  
  /**
   * Register a callback for agent status updates
   */
  onStatus(callback: StatusCallback) {
    this.statusCallbacks.push(callback);
    return () => {
      this.statusCallbacks = this.statusCallbacks.filter(cb => cb !== callback);
    };
  }
  
  /**
   * Register a callback for message events
   */
  onMessage(callback: MessageCallback) {
    this.messageCallbacks.push(callback);
    return () => {
      this.messageCallbacks = this.messageCallbacks.filter(cb => cb !== callback);
    };
  }
  
  /**
   * Send a message through the WebSocket
   */
  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.error('WebSocket is not connected');
    }
  }
  
  /**
   * Analyze a request with real-time status updates
   */
  async analyze(topic: string, chatHistory: string[] = []): Promise<AnalysisResponse> {
    await this.connect();
    
    return new Promise((resolve, reject) => {
      const cleanup = this.onMessage((type, data) => {
        if (type === 'analysis_complete') {
          cleanup();
          resolve(data as AnalysisResponse);
        } else if (type === 'error') {
          cleanup();
          reject(new Error(data.message || 'Analysis failed'));
        }
      });
      
      this.send({ action: 'analyze', topic, chatHistory });
    });
  }
  
  /**
   * Generate a plan with real-time status updates
   */
  async generate(
    topic: string, 
    context: string, 
    file?: UploadedFile
  ): Promise<ProjectData> {
    await this.connect();
    
    return new Promise((resolve, reject) => {
      const cleanup = this.onMessage((type, data) => {
        if (type === 'generation_complete') {
          cleanup();
          resolve(data as ProjectData);
        } else if (type === 'error') {
          cleanup();
          reject(new Error(data.message || 'Generation failed'));
        }
      });
      
      this.send({ action: 'generate', topic, context, file });
    });
  }
  
  /**
   * Chat with the manager with real-time status updates
   */
  async chat(
    project: ProjectData, 
    message: string, 
    history: ChatMessage[]
  ): Promise<ChatResponse> {
    await this.connect();
    
    return new Promise((resolve, reject) => {
      const cleanup = this.onMessage((type, data) => {
        if (type === 'chat_complete') {
          cleanup();
          resolve(data as ChatResponse);
        } else if (type === 'error') {
          cleanup();
          reject(new Error(data.message || 'Chat failed'));
        }
      });
      
      this.send({ action: 'chat', project, message, history });
    });
  }
}

// Export singleton instance
export const wsService = new WebSocketService();

// --- Legacy compatibility layer ---
// These functions maintain backwards compatibility with the old geminiService API

/**
 * @deprecated Use wsService.analyze() for real-time updates
 */
export const checkFileRelevance = async (topic: string, file: UploadedFile) => {
  // This is now handled server-side during plan generation
  return { isRelevant: true, reason: "File relevance checked server-side" };
};

/**
 * @deprecated Use wsService.generate() for real-time updates
 */
export const createProjectStructure = async (
  topic: string, 
  context: string, 
  critique?: string,
  file?: UploadedFile
) => {
  const result = await generatePlan(topic, context, file);
  return result.project;
};

/**
 * @deprecated Structure validation is now handled server-side
 */
export const validateStructure = async (plan: any) => {
  return { isValid: true, critique: "" };
};

/**
 * @deprecated Estimation is now handled server-side
 */
export const estimateProjectTimelines = async (plan: any, critique?: string) => {
  return plan;
};

/**
 * @deprecated Estimate validation is now handled server-side
 */
export const validateEstimates = async (plan: any) => {
  return { isValid: true, critique: "" };
};

/**
 * @deprecated Final review is now handled server-side
 */
export const reviewAndRefinePlan = async (plan: any) => {
  return plan;
};

/**
 * @deprecated Use chatWithManager() or wsService.chat()
 */
export const chatWithProjectManager = chatWithManager;

/**
 * Recalculate schedule - now just passes through since backend handles it
 */
export const recalculateSchedule = (tasks: Task[]): Task[] => {
  // Schedule calculation is now done server-side
  // This is kept for local edits that don't go through the API
  const taskMap = new Map<string, Task>();
  tasks.forEach(t => taskMap.set(t.id, { ...t, startOffset: 0 }));

  const visited = new Set<string>();
  const visiting = new Set<string>();

  const calculateStart = (taskId: string): number => {
    if (visiting.has(taskId)) {
      console.warn("Circular dependency detected:", taskId);
      return 0;
    }
    if (visited.has(taskId)) {
      return taskMap.get(taskId)!.startOffset;
    }

    visiting.add(taskId);
    const task = taskMap.get(taskId);
    
    let maxDependencyEnd = 0;
    if (task && task.dependencies) {
      for (const depId of task.dependencies) {
        if (taskMap.has(depId)) {
          const depStart = calculateStart(depId);
          const depTask = taskMap.get(depId)!;
          const depEnd = depStart + (depTask.duration || 0) + (depTask.buffer || 0);
          if (depEnd > maxDependencyEnd) {
            maxDependencyEnd = depEnd;
          }
        }
      }
    }

    if (task) {
      task.startOffset = maxDependencyEnd;
    }
    
    visiting.delete(taskId);
    visited.add(taskId);
    return maxDependencyEnd;
  };

  tasks.forEach(t => calculateStart(t.id));
  return Array.from(taskMap.values()).sort((a, b) => a.startOffset - b.startOffset);
};
