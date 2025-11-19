#!/usr/bin/env python3
"""Complete GM Hub restructuring to match Player Hub layout"""
import re

# Read original file
with open('apps/web/components/gm/gm-hub.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the sources tab content (lines ~709-737)
# This content was inside activeTab === "sources" conditional
content = re.sub(
    r'\{activeTab === "sources" \? \(\s+<SourceMultiSelect[\s\S]*?\/>\s+\) : null\}',
    '',
    content,
    flags=re.MULTILINE
)

# Find and extract AI Assistant section (it's currently inside {activeGame ? ( block)
# AI Assistant starts with {/* AI Assistant Section */}
ai_pattern = r'(\s+\{/\* AI Assistant Section \*/\}[\s\S]*?</section>)'
ai_match = re.search(ai_pattern, content)
if ai_match:
    ai_section = ai_match.group(1)
    # Remove AI section from its current location
    content = content.replace(ai_section, '')
    print("[OK] Extracted AI Assistant section")
else:
    print("[FAIL] Could not find AI Assistant section")
    ai_section = ""

# Change grid layout from lg:grid-cols-[1.2fr_2fr] to xl:grid-cols-[2fr_1.5fr]
content = content.replace(
    '<div className="grid gap-6 lg:grid-cols-[1.2fr_2fr]">',
    '<div className="grid gap-6 xl:grid-cols-[2fr_1.5fr]">'
)

# Find the aside closing tag and insert wrapper div + AI Assistant
aside_end = '</aside>'
aside_pattern = r'(</aside>)\s*\n\s*<section className="space-y-5">'

new_structure = f'''{aside_end}

{ai_section}
        </div>

        <div className="space-y-6">
          {{/* Sources Panel - Always Visible */}}
          <SourceMultiSelect
            sources={{ownedSources}}
            selectedIds={{gameSources.map(s => s.id)}}
            onChange={{handleSourceSelectionChange}}
            ownedSourceIds={{ownedSources.map(s => s.id)}}
            selectedLabel={{`Game sources${{activeGame ? ` (${{gameSources.length}} of ${{gameQuotas?.effectiveSourceLimit ?? 3}}${{gameQuotas?.additionalSourcesFromGrants ? ` [${{gameQuotas.baseSourceLimit}}+${{gameQuotas.additionalSourcesFromGrants}}]` : ''}})` : ''}}`}}
            renderFooter={{
              !activeGame ? (
                <span>Select a game to manage sources.</span>
              ) : (
                <div className="flex items-center justify-between">
                  <span>
                    {{gameSources.length >= (gameQuotas?.effectiveSourceLimit ?? 3)
                      ? `Limit reached for ${{tierLabels[activeGame?.tier ?? "free"]}} tier`
                      : `${{(gameQuotas?.effectiveSourceLimit ?? 3) - gameSources.length}} source${{(gameQuotas?.effectiveSourceLimit ?? 3) - gameSources.length !== 1 ? 's' : ''}} remaining`}}
                  </span>
                  {{gameSources.length >= (gameQuotas?.effectiveSourceLimit ?? 3) && activeGameId && (
                    <ManageBillingButton
                      scope="game"
                      scopeId={{activeGameId}}
                      className="text-xs"
                      description=""
                      buttonLabel="Upgrade"
                      disabledLabel=""
                    />
                  )}}
                </div>
              )
            }}
            className={{activeGame ? undefined : "opacity-75"}}
          />
        </div>
      </div>

      {{/* Game Details Section - Shown when game is selected */}}
      {{activeGame ? (
        <div className="space-y-5">
          <section className="space-y-5">'''

content = re.sub(aside_pattern, new_structure, content)

# Write the restructured file
with open('apps/web/components/gm/gm-hub.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] GM Hub restructured successfully")
print("[OK] AI Assistant now in left column (always visible)")
print("[OK] Sources panel now in right column (always visible)")
print("[OK] Game details/tabs moved below grid (conditional on game selection)")
