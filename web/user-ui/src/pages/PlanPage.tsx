import React from 'react';
import { useThemeStore } from '../stores/themeStore';
import { PlanPlay, Cpu, Layers, Clock } from 'lucide-react';

export default function PlanPage() {
  const { theme } = useThemeStore();
  const isTerminal = theme === 'terminal';

  return (
    <div className="h-full p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className={`mb-8 ${isTerminal ? 'text-terminal-text' : 'text-white'}`}>
          <div className="flex items-center gap-3 mb-4">
            <PlanPlay className={`h-8 w-8 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-orange'}`} />
            <h1 className={`text-3xl font-bold ${isTerminal ? 'font-mono' : 'font-lcars'}`}>
              {isTerminal ? 'WORKFLOW_PLANNER' : 'TACTICAL PLANNING'}
            </h1>
          </div>
          <p className={`${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
            {isTerminal
              ? 'Advanced workflow planning and execution management system'
              : 'Strategic workflow design and resource allocation interface'
            }
          </p>
        </div>

        {/* Coming Soon Content */}
        <div className={`
          text-center py-16
          ${isTerminal
            ? 'border-2 border-dashed border-terminal-text/20 bg-black/20'
            : 'border-2 border-dashed border-lcars-orange/30 bg-lcars-panel/10'
          }
        `}>
          <div className={`text-6xl mb-6 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-orange'}`}>
            <PlanPlay className="h-16 w-16 mx-auto" />
          </div>

          <h2 className={`text-2xl font-bold mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
            {isTerminal ? 'PLANNING_INTERFACE_V2.0' : 'TACTICAL INTERFACE'}
          </h2>

          <p className={`text-lg mb-8 ${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
            Advanced workflow planning coming in next update
          </p>

          {/* Feature Preview */}
          <div className="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto">
            {[
              {
                icon: Cpu,
                title: isTerminal ? 'PROCESS_DESIGN' : 'Process Design',
                desc: 'Interactive workflow builder'
              },
              {
                icon: Layers,
                title: isTerminal ? 'STEP_MANAGEMENT' : 'Step Management',
                desc: 'Hierarchical task organization'
              },
              {
                icon: Clock,
                title: isTerminal ? 'TIME_ESTIMATION' : 'Time Estimation',
                desc: 'Resource and duration planning'
              }
            ].map(({ icon: Icon, title, desc }, index) => (
              <div
                key={index}
                className={`
                  p-4 rounded-lg
                  ${isTerminal
                    ? 'bg-terminal-text/5 border border-terminal-text/20'
                    : 'bg-lcars-panel/20 border border-lcars-orange/20'
                  }
                `}
              >
                <Icon className={`h-8 w-8 mx-auto mb-3 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-orange'}`} />
                <h3 className={`font-bold mb-2 ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
                  {title}
                </h3>
                <p className={`text-sm ${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Tip */}
        <div className={`
          mt-6 p-4 rounded-lg text-center
          ${isTerminal
            ? 'bg-terminal-amber/10 border border-terminal-amber/20 text-terminal-amber'
            : 'bg-lcars-yellow/10 border border-lcars-yellow/20 text-lcars-yellow'
          }
        `}>
          <p className={`text-sm ${isTerminal ? 'font-mono' : 'font-lcars'}`}>
            {isTerminal
              ? 'TIP: Use the chat interface to request workflow planning - it will automatically redirect here when ready.'
              : 'Tip: Planning requests from the communication channel will be processed here when the interface is complete.'
            }
          </p>
        </div>
      </div>
    </div>
  );
}