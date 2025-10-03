/**
 * Query Suggestions Component
 *
 * Intelligent query suggestions based on input analysis and common patterns
 */

import React, { useState, useEffect } from 'react';
import { Search, Brain, Sparkles, BookOpen, Wand2, TrendingUp } from 'lucide-react';

interface QuerySuggestionsProps {
  query: string;
  onSelect: (suggestion: string) => void;
  theme: 'terminal' | 'lcars';
}

interface Suggestion {
  text: string;
  category: 'rules' | 'planning' | 'creative' | 'howto' | 'popular';
  confidence: number;
}

export default function QuerySuggestions({ query, onSelect, theme }: QuerySuggestionsProps) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);

  const isTerminal = theme === 'terminal';

  useEffect(() => {
    const generateSuggestions = async () => {
      if (query.length < 3) {
        setSuggestions([]);
        return;
      }

      setLoading(true);

      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 200));

      const queryLower = query.toLowerCase();
      const allSuggestions: Suggestion[] = [
        // Rules-based suggestions
        {
          text: 'What are the basic rules of D&D combat?',
          category: 'rules',
          confidence: queryLower.includes('combat') || queryLower.includes('fight') ? 0.9 : 0.3
        },
        {
          text: 'How do spell slots work in D&D 5e?',
          category: 'rules',
          confidence: queryLower.includes('spell') || queryLower.includes('magic') ? 0.95 : 0.2
        },
        {
          text: 'Explain armor class and how it works',
          category: 'rules',
          confidence: queryLower.includes('armor') || queryLower.includes('ac') ? 0.9 : 0.2
        },
        {
          text: 'What dice do I need for tabletop RPGs?',
          category: 'rules',
          confidence: queryLower.includes('dice') || queryLower.includes('roll') ? 0.85 : 0.2
        },

        // Planning suggestions
        {
          text: 'Plan a character creation workflow for new players',
          category: 'planning',
          confidence: queryLower.includes('character') || queryLower.includes('create') ? 0.8 : 0.3
        },
        {
          text: 'Create a session 0 checklist for new campaigns',
          category: 'planning',
          confidence: queryLower.includes('session') || queryLower.includes('campaign') ? 0.8 : 0.2
        },
        {
          text: 'Plan a dungeon exploration workflow',
          category: 'planning',
          confidence: queryLower.includes('dungeon') || queryLower.includes('explore') ? 0.8 : 0.2
        },

        // Creative suggestions
        {
          text: 'Design a custom magic item with balanced stats',
          category: 'creative',
          confidence: queryLower.includes('design') || queryLower.includes('create') ? 0.7 : 0.2
        },
        {
          text: 'Generate a tavern with NPCs and plot hooks',
          category: 'creative',
          confidence: queryLower.includes('tavern') || queryLower.includes('npc') ? 0.8 : 0.2
        },
        {
          text: 'Create a backstory for a rogue character',
          category: 'creative',
          confidence: queryLower.includes('backstory') || queryLower.includes('character') ? 0.7 : 0.2
        },

        // How-to suggestions
        {
          text: 'How to be a good dungeon master for beginners',
          category: 'howto',
          confidence: queryLower.includes('dm') || queryLower.includes('master') ? 0.8 : 0.3
        },
        {
          text: 'How to handle player character death respectfully',
          category: 'howto',
          confidence: queryLower.includes('death') || queryLower.includes('die') ? 0.8 : 0.2
        },
        {
          text: 'How to run social encounters and roleplay',
          category: 'howto',
          confidence: queryLower.includes('social') || queryLower.includes('roleplay') ? 0.8 : 0.2
        },

        // Popular suggestions
        {
          text: 'What\'s the difference between D&D 5e and Pathfinder?',
          category: 'popular',
          confidence: queryLower.includes('dnd') || queryLower.includes('pathfinder') ? 0.7 : 0.4
        },
        {
          text: 'Best starting adventures for new D&D groups',
          category: 'popular',
          confidence: queryLower.includes('adventure') || queryLower.includes('start') ? 0.7 : 0.3
        },
        {
          text: 'Essential apps and tools for running D&D games',
          category: 'popular',
          confidence: queryLower.includes('tools') || queryLower.includes('app') ? 0.8 : 0.3
        }
      ];

      // Filter and score suggestions based on query similarity
      const relevantSuggestions = allSuggestions
        .map(suggestion => {
          let score = suggestion.confidence;

          // Boost score based on word matches
          const suggestionWords = suggestion.text.toLowerCase().split(' ');
          const queryWords = queryLower.split(' ');

          queryWords.forEach(queryWord => {
            if (queryWord.length > 2) {
              suggestionWords.forEach(suggestionWord => {
                if (suggestionWord.includes(queryWord) || queryWord.includes(suggestionWord)) {
                  score += 0.1;
                }
              });
            }
          });

          return { ...suggestion, confidence: Math.min(score, 1) };
        })
        .filter(suggestion => suggestion.confidence > 0.3)
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5);

      setSuggestions(relevantSuggestions);
      setLoading(false);
    };

    generateSuggestions();
  }, [query]);

  if (suggestions.length === 0 && !loading) {
    return null;
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'rules': return <BookOpen className="h-3 w-3" />;
      case 'planning': return <Brain className="h-3 w-3" />;
      case 'creative': return <Wand2 className="h-3 w-3" />;
      case 'howto': return <Search className="h-3 w-3" />;
      case 'popular': return <TrendingUp className="h-3 w-3" />;
      default: return <Sparkles className="h-3 w-3" />;
    }
  };

  const getCategoryColor = (category: string) => {
    if (isTerminal) {
      return 'text-terminal-amber';
    }

    switch (category) {
      case 'rules': return 'text-lcars-blue';
      case 'planning': return 'text-lcars-purple';
      case 'creative': return 'text-lcars-orange';
      case 'howto': return 'text-lcars-yellow';
      case 'popular': return 'text-lcars-red';
      default: return 'text-lcars-orange';
    }
  };

  return (
    <div className={`
      absolute top-full left-0 right-0 mt-1 z-50
      ${isTerminal
        ? 'bg-black/95 border border-terminal-text/30 backdrop-blur-sm'
        : 'bg-lcars-panel/95 border border-lcars-orange backdrop-blur-sm'
      }
      rounded-md shadow-lg max-h-60 overflow-y-auto
    `}>
      {loading ? (
        <div className={`p-3 text-center text-sm ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
          Analyzing query...
        </div>
      ) : (
        <div className="py-2">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => onSelect(suggestion.text)}
              className={`
                w-full px-3 py-2 text-left text-sm transition-colors
                flex items-start gap-2 group
                ${isTerminal
                  ? 'hover:bg-terminal-text/10 text-terminal-text'
                  : 'hover:bg-white/10 text-white'
                }
              `}
            >
              <div className={`mt-0.5 ${getCategoryColor(suggestion.category)}`}>
                {getCategoryIcon(suggestion.category)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="truncate">{suggestion.text}</div>
                <div className={`text-xs mt-1 flex items-center gap-2 ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
                  <span className="capitalize">{suggestion.category}</span>
                  <span>•</span>
                  <span>Confidence: {Math.round(suggestion.confidence * 100)}%</span>
                </div>
              </div>
            </button>
          ))}

          <div className={`px-3 py-2 border-t ${isTerminal ? 'border-terminal-text/20 text-terminal-text/50' : 'border-white/20 text-white/50'} text-xs`}>
            💡 Suggestions based on your query pattern and popular requests
          </div>
        </div>
      )}
    </div>
  );
}