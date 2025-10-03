/**
 * Intent Classifier Component
 *
 * Visual indicator for query intent classification and routing decisions
 */

import React from 'react';
import {
  Search,
  BookOpen,
  Wand2,
  Code,
  FileText,
  Network,
  Brain,
  Target,
  Zap
} from 'lucide-react';

interface IntentClassifierProps {
  intent: 'fact_lookup' | 'procedural_howto' | 'creative_write' | 'code_help' | 'summarize' | 'multi_hop_reasoning' | 'planning';
  confidence: number;
  domain: string;
  complexity: 'simple' | 'moderate' | 'complex';
  theme: 'terminal' | 'lcars';
}

export default function IntentClassifier({
  intent,
  confidence,
  domain,
  complexity,
  theme
}: IntentClassifierProps) {
  const isTerminal = theme === 'terminal';

  const getIntentInfo = () => {
    switch (intent) {
      case 'fact_lookup':
        return {
          icon: Search,
          label: 'Fact Lookup',
          description: 'Direct information retrieval',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-blue'
        };
      case 'procedural_howto':
        return {
          icon: BookOpen,
          label: 'How-To Guide',
          description: 'Step-by-step instructions',
          color: isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'
        };
      case 'creative_write':
        return {
          icon: Wand2,
          label: 'Creative Writing',
          description: 'Content generation',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-orange'
        };
      case 'code_help':
        return {
          icon: Code,
          label: 'Code Assistance',
          description: 'Programming support',
          color: isTerminal ? 'text-terminal-amber' : 'text-lcars-purple'
        };
      case 'summarize':
        return {
          icon: FileText,
          label: 'Summarization',
          description: 'Content summary',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-green'
        };
      case 'multi_hop_reasoning':
        return {
          icon: Network,
          label: 'Complex Reasoning',
          description: 'Multi-step analysis',
          color: isTerminal ? 'text-terminal-amber' : 'text-lcars-red'
        };
      case 'planning':
        return {
          icon: Brain,
          label: 'Workflow Planning',
          description: 'Task orchestration',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-blue'
        };
      default:
        return {
          icon: Target,
          label: 'General Query',
          description: 'Standard processing',
          color: isTerminal ? 'text-terminal-text/70' : 'text-white/70'
        };
    }
  };

  const getComplexityInfo = () => {
    switch (complexity) {
      case 'simple':
        return {
          label: 'Simple',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-green',
          bgColor: isTerminal ? 'bg-terminal-text/10' : 'bg-lcars-green/20'
        };
      case 'moderate':
        return {
          label: 'Moderate',
          color: isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow',
          bgColor: isTerminal ? 'bg-terminal-amber/10' : 'bg-lcars-yellow/20'
        };
      case 'complex':
        return {
          label: 'Complex',
          color: isTerminal ? 'text-red-400' : 'text-lcars-red',
          bgColor: isTerminal ? 'bg-red-400/10' : 'bg-lcars-red/20'
        };
      default:
        return {
          label: 'Unknown',
          color: isTerminal ? 'text-terminal-text/50' : 'text-white/50',
          bgColor: isTerminal ? 'bg-terminal-text/5' : 'bg-white/10'
        };
    }
  };

  const intentInfo = getIntentInfo();
  const complexityInfo = getComplexityInfo();
  const Icon = intentInfo.icon;

  return (
    <div className={`
      inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs
      ${isTerminal
        ? 'bg-terminal-text/5 border border-terminal-text/20'
        : 'bg-lcars-panel/20 border border-lcars-orange/30'
      }
    `}>
      {/* Intent */}
      <div className="flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${intentInfo.color}`} />
        <div>
          <div className={`font-medium ${intentInfo.color}`}>
            {intentInfo.label}
          </div>
          <div className={`text-xs ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
            {intentInfo.description}
          </div>
        </div>
      </div>

      {/* Separator */}
      <div className={`w-px h-6 ${isTerminal ? 'bg-terminal-text/20' : 'bg-white/20'}`} />

      {/* Domain */}
      <div className="text-center">
        <div className={`font-medium ${isTerminal ? 'text-terminal-text' : 'text-white'}`}>
          {domain.toUpperCase()}
        </div>
        <div className={`text-xs ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
          Domain
        </div>
      </div>

      {/* Separator */}
      <div className={`w-px h-6 ${isTerminal ? 'bg-terminal-text/20' : 'bg-white/20'}`} />

      {/* Complexity */}
      <div className="text-center">
        <div className={`
          px-2 py-0.5 rounded text-xs font-medium
          ${complexityInfo.color} ${complexityInfo.bgColor}
        `}>
          {complexityInfo.label}
        </div>
        <div className={`text-xs mt-0.5 ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
          Complexity
        </div>
      </div>

      {/* Confidence */}
      <div className="text-center">
        <div className={`flex items-center gap-1`}>
          <Zap className={`h-3 w-3 ${confidence > 0.8 ? (isTerminal ? 'text-terminal-text' : 'text-lcars-green') : (isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow')}`} />
          <span className={`font-medium text-xs ${isTerminal ? 'text-terminal-text' : 'text-white'}`}>
            {Math.round(confidence * 100)}%
          </span>
        </div>
        <div className={`text-xs ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
          Confidence
        </div>
      </div>
    </div>
  );
}