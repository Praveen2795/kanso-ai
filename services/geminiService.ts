import { GoogleGenAI, Type, Schema } from "@google/genai";
import { Task, ProjectData } from "../types";

// Helper to get client
const getClient = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("API Key missing");
  return new GoogleGenAI({ apiKey });
};

// --- schemas ---

const clarificationSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    needsClarification: { type: Type.BOOLEAN },
    questions: { 
      type: Type.ARRAY, 
      items: { type: Type.STRING } 
    },
    reasoning: { type: Type.STRING }
  },
  required: ["needsClarification", "reasoning"]
};

const subtaskSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    name: { type: Type.STRING },
    description: { type: Type.STRING },
    duration: { type: Type.NUMBER, description: "Duration in hours" }
  },
  required: ["name", "duration"]
};

const taskSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    id: { type: Type.STRING },
    name: { type: Type.STRING },
    phase: { type: Type.STRING },
    description: { type: Type.STRING },
    complexity: { type: Type.STRING, enum: ["Low", "Medium", "High"] },
    subtasks: {
      type: Type.ARRAY,
      items: subtaskSchema
    },
    dependencies: { 
      type: Type.ARRAY, 
      items: { type: Type.STRING } 
    },
    estimatedHours: { type: Type.NUMBER },
    recommendedBufferHours: { type: Type.NUMBER },
    startOffsetHours: { type: Type.NUMBER }
  },
  required: ["id", "name", "phase", "estimatedHours", "recommendedBufferHours", "startOffsetHours", "complexity", "subtasks"]
};

const projectPlanSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    projectTitle: { type: Type.STRING },
    projectSummary: { type: Type.STRING },
    assumptions: {
      type: Type.ARRAY,
      items: { type: Type.STRING },
      description: "List of assumptions made if user input was vague or URLs were inaccessible."
    },
    tasks: { 
      type: Type.ARRAY, 
      items: taskSchema 
    }
  },
  required: ["projectTitle", "tasks"]
};

// --- Algorithms ---

// Deterministic scheduler to ensure no overlaps on dependencies
export const recalculateSchedule = (tasks: Task[]): Task[] => {
  // Create a map for quick access
  const taskMap = new Map<string, Task>();
  tasks.forEach(t => taskMap.set(t.id, { ...t, startOffset: 0 })); // Reset offsets to recalculate

  const visited = new Set<string>();
  const visiting = new Set<string>();

  const calculateStart = (taskId: string): number => {
    if (visiting.has(taskId)) {
      console.warn("Circular dependency detected:", taskId);
      return 0; // Break cycle
    }
    if (visited.has(taskId)) {
      return taskMap.get(taskId)!.startOffset;
    }

    visiting.add(taskId);
    const task = taskMap.get(taskId);
    
    let maxDependencyEnd = 0;
    if (task && task.dependencies) {
      for (const depId of task.dependencies) {
        // Dependency must exist
        if (taskMap.has(depId)) {
          const depStart = calculateStart(depId);
          const depTask = taskMap.get(depId)!;
          // The current task starts after the dependency finishes (duration + buffer)
          const depEnd = depStart + depTask.duration + (depTask.buffer || 0);
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

  // Run calculation for all tasks
  tasks.forEach(t => calculateStart(t.id));

  // Sort by start time for cleaner UI
  return Array.from(taskMap.values()).sort((a, b) => a.startOffset - b.startOffset);
};


// --- Agents ---

export const analyzeRequest = async (topic: string, chatHistory: string[] = []) => {
  const client = getClient();
  const prompt = `
    You are the ANALYST Agent. Your goal is to deeply understand the user's project request.
    
    User Topic: "${topic}"
    Previous Context: ${JSON.stringify(chatHistory)}

    1. **Verify Technical Terms**: Use Google Search to check if terms exist.
    2. **Link Detection**: If the user provided a URL, check if it's accessible via Google Search.
    3. **Identify Ambiguity**: If context is missing (skill level, deadline, scale), ask for it.
    
    Generate 2-3 **SMART** questions. If a URL was provided but seems broken or irrelevant, ask about it.
    Guardrails: Reject illegal/harmful topics.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview",
    contents: prompt,
    config: {
      tools: [{ googleSearch: {} }],
      responseMimeType: "application/json",
      responseSchema: clarificationSchema,
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * ARCHITECT AGENT
 * Focus: Structure, Dependencies, Scope.
 * Ignores precise time estimation.
 */
export const createProjectStructure = async (topic: string, context: string) => {
  const client = getClient();
  
  const prompt = `
    You are the ARCHITECT Agent.
    
    Goal: Create the STRUCTURAL BACKBONE of a project plan for: "${topic}".
    User Context: "${context}"

    **Instructions:**
    1. **Research & URLs**: Use Google Search. If user provided a URL, prioritize it. If inaccessible, note in 'assumptions'.
    2. **Breakdown**: Create Phases -> Tasks -> Subtasks.
       - Each Task MUST have at least 3-5 concrete subtasks.
    3. **Dependencies**: Define logical order (Task B depends on Task A).
    4. **Output**: Return the JSON structure. 
       - Set 'estimatedHours' and 'duration' to 0 or placeholders. The Estimator Agent will fix them later.
    
    Output pure JSON.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview",
    contents: prompt,
    config: {
      tools: [{ googleSearch: {} }],
      responseMimeType: "application/json",
      responseSchema: projectPlanSchema,
      thinkingConfig: { thinkingBudget: 2048 }
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * ESTIMATOR AGENT
 * Focus: Realistic Bottom-Up Estimation.
 * Fills in the time gaps left by the Architect.
 */
export const estimateProjectTimelines = async (architectPlan: any) => {
  const client = getClient();

  const prompt = `
    You are the ESTIMATOR Agent.
    
    Input: A project structure created by the Architect.
    ${JSON.stringify(architectPlan)}

    **Your Goal: Perform a Bottom-Up Estimation.**
    
    1. **Iterate through every single task.**
    2. **Iterate through every subtask** within that task.
    3. **Estimate Duration**: Assign a realistic duration (in hours) to EACH subtask.
       - Consider the 'complexity' level.
       - Be conservative. Things take longer than expected.
    4. **Aggregation**: The 'estimatedHours' for the parent Task MUST be the sum of its subtasks.
    5. **Buffers**: Add a 'recommendedBufferHours' (approx 20% of total) to the parent task.

    Return the fully updated JSON with numbers filled in.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview", // Using Pro for better reasoning on numbers
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: projectPlanSchema,
    }
  });

  const plan = JSON.parse(response.text || "{}");
  if (plan.tasks) {
    plan.tasks = recalculateSchedule(plan.tasks);
  }
  return plan;
}

export const reviewAndRefinePlan = async (currentPlan: any) => {
  const client = getClient();

  const prompt = `
    You are the REVIEWER Agent. 
    
    Review the following project plan JSON:
    ${JSON.stringify(currentPlan)}

    Checklist:
    1. **Subtask Check**: Do tasks have concrete subtasks with specific durations? If not, add/fix them.
    2. **Complexity Check**: Is the complexity flag accurate?
    3. **Timeline Reality**: Are durations realistic for the complexity?
    4. **Assumptions Check**: Ensure any fallback assumptions about URLs are clearly stated.
    
    Return the cleaned, validated JSON.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-flash-preview", 
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: projectPlanSchema,
    }
  });

  const plan = JSON.parse(response.text || "{}");
  if (plan.tasks) {
    plan.tasks = recalculateSchedule(plan.tasks);
  }
  return plan;
};

export const chatWithProjectManager = async (
  currentPlan: ProjectData, 
  userMessage: string, 
  history: {role: string, content: string}[]
) => {
  const client = getClient();
  
  const systemInstruction = `
    You are the Project Manager Agent.
    Current Project: ${JSON.stringify(currentPlan)}
    
    User Request: "${userMessage}"
    
    **Instructions:**
    1. **Safety & Relevance Guardrails**: 
       - IF the user asks about dangerous, illegal, sexually explicit, or hateful topics: Refuse immediately.
       - IF the user asks about topics completely unrelated to project planning or the current project (e.g. "Write a poem about dogs", "Who won the 1990 world cup"): Politely decline and steer back to the plan.
    
    2. **URL Handling**: If the user's message contains a URL, use Google Search to find information about it.
       - If you can access/verify it, use that info to refine the plan.
       - If you CANNOT access it, explicit state in 'reply': "I couldn't access that link, so I'm making assumptions based on your description." and proceed with best-guess updates.
    
    3. **Task ID Persistence**: When updating the plan, you MUST preserve the existing 'id' of tasks unless you are deliberately deleting them. Do not regenerate random IDs for existing tasks, or the dependencies will break.
       
    4. **Plan Updates**: If the user asks to change the plan, return "updatedPlan".
       - Recalculate dependencies if needed.
    
    Return JSON with 'reply' and optional 'updatedPlan'.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview", 
    contents: userMessage,
    config: {
      tools: [{ googleSearch: {} }],
      systemInstruction: systemInstruction,
      responseMimeType: "application/json",
    }
  });

  return JSON.parse(response.text || "{}");
}