#!/usr/bin/env python3
"""
Generate test PDF fixtures for Phase 1 ingestion pipeline validation.
Creates realistic TTRPG content for testing the three-pass pipeline.
"""

import os
from pathlib import Path

def create_test_pdf_content():
    """
    Generate test PDFs using basic text content that can be written to files.
    Since we don't have reportlab, we'll create HTML files that can be converted to PDFs manually.
    """
    
    fixtures_dir = Path("test_fixtures")
    fixtures_dir.mkdir(exist_ok=True)
    
    # Test PDF 1: Basic D&D Character Creation Guide
    dnd_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>D&D Character Creation Guide</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #8B0000; }
            h2 { color: #4B0082; }
        </style>
    </head>
    <body>
        <h1>Dungeons & Dragons Character Creation Guide</h1>
        
        <h2>Chapter 1: Race Selection</h2>
        <p>Choosing your character's race is the first major decision in D&D character creation. Each race provides specific ability score increases, traits, and cultural background that shape your character's identity and capabilities.</p>
        
        <p><strong>Human:</strong> Versatile and adaptable, humans receive a +1 to all ability scores. They are excellent for any class and provide flexibility in character builds.</p>
        
        <p><strong>Elf:</strong> Graceful and long-lived, elves receive a +2 to Dexterity. They have keen senses, fey ancestry, and proficiency with certain weapons.</p>
        
        <h2>Chapter 2: Class Features</h2>
        <p>Your character class determines your core abilities, hit points, proficiencies, and how you contribute to your adventuring party.</p>
        
        <p><strong>Fighter:</strong> Masters of martial combat, fighters can use all armor and weapons. They gain Second Wind for self-healing and Action Surge for additional actions.</p>
        
        <p><strong>Wizard:</strong> Scholars of arcane magic, wizards cast spells using their Intelligence. They prepare spells from a spellbook and can learn new spells as they advance.</p>
        
        <h2>Chapter 3: Ability Scores</h2>
        <p>Six ability scores define your character's basic capabilities: Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma.</p>
        
        <p>Roll 4d6, drop the lowest die, and record the total. Repeat this process six times to generate your ability scores, then assign them to the six abilities as desired.</p>
    </body>
    </html>
    """
    
    # Test PDF 2: Combat Mechanics Reference
    combat_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTRPG Combat Mechanics</title>
        <style>
            body { font-family: Georgia, serif; margin: 40px; }
            h1 { color: #2F4F4F; }
            h2 { color: #8B4513; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>Combat Mechanics Reference</h1>
        
        <h2>Initiative and Turn Order</h2>
        <p>At the start of combat, each participant rolls initiative by making a Dexterity check. The DM ranks all combatants in order from highest to lowest initiative result. This is the order in which they act during each round.</p>
        
        <h2>Actions in Combat</h2>
        <p>On your turn, you can move and take one action. You can also take one bonus action and any number of free actions.</p>
        
        <table>
            <tr>
                <th>Action Type</th>
                <th>Description</th>
                <th>Examples</th>
            </tr>
            <tr>
                <td>Action</td>
                <td>The main thing you do on your turn</td>
                <td>Attack, Cast a Spell, Dash, Help</td>
            </tr>
            <tr>
                <td>Bonus Action</td>
                <td>Quick additional activity</td>
                <td>Off-hand attack, certain spells</td>
            </tr>
            <tr>
                <td>Reaction</td>
                <td>Response to a trigger</td>
                <td>Opportunity attack, counterspell</td>
            </tr>
        </table>
        
        <h2>Attack Rolls</h2>
        <p>To make an attack roll, roll a d20 and add your ability modifier and proficiency bonus (if applicable). If the total equals or exceeds the target's Armor Class (AC), the attack hits.</p>
        
        <p><strong>Critical Hits:</strong> When you roll a natural 20 on an attack roll, you score a critical hit. Roll all damage dice twice and add your normal damage modifiers.</p>
        
        <h2>Damage and Hit Points</h2>
        <p>When you take damage, you lose hit points. If you reach 0 hit points, you fall unconscious and must make death saving throws on subsequent turns.</p>
    </body>
    </html>
    """
    
    # Test PDF 3: Spell Compendium
    spell_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spell Compendium</title>
        <style>
            body { font-family: 'Times New Roman', serif; margin: 40px; }
            h1 { color: #4B0082; text-align: center; }
            h2 { color: #8B0000; }
            .spell { border: 1px solid #ccc; padding: 15px; margin: 10px 0; }
            .spell-name { font-weight: bold; color: #4B0082; }
        </style>
    </head>
    <body>
        <h1>Arcane Spell Compendium</h1>
        
        <h2>1st Level Spells</h2>
        
        <div class="spell">
            <div class="spell-name">Magic Missile</div>
            <p><strong>Casting Time:</strong> 1 action<br>
            <strong>Range:</strong> 120 feet<br>
            <strong>Components:</strong> V, S<br>
            <strong>Duration:</strong> Instantaneous</p>
            <p>You create three glowing darts of magical force. Each dart hits a creature of your choice within range, dealing 1d4 + 1 force damage. The darts strike simultaneously.</p>
        </div>
        
        <div class="spell">
            <div class="spell-name">Shield</div>
            <p><strong>Casting Time:</strong> 1 reaction<br>
            <strong>Range:</strong> Self<br>
            <strong>Components:</strong> V, S<br>
            <strong>Duration:</strong> 1 round</p>
            <p>An invisible barrier of magical force appears around you, granting a +5 bonus to AC and immunity to magic missile spells.</p>
        </div>
        
        <h2>2nd Level Spells</h2>
        
        <div class="spell">
            <div class="spell-name">Fireball</div>
            <p><strong>Casting Time:</strong> 1 action<br>
            <strong>Range:</strong> 150 feet<br>
            <strong>Components:</strong> V, S, M (a tiny ball of bat guano and sulfur)<br>
            <strong>Duration:</strong> Instantaneous</p>
            <p>A bright streak flashes from your pointing finger to a point within range and blossoms into an explosion of flame. Each creature in a 20-foot-radius sphere must make a Dexterity saving throw, taking 8d6 fire damage on failure or half on success.</p>
        </div>
        
        <h2>Spellcasting Mechanics</h2>
        <p>To cast a spell, you must expend a spell slot of the spell's level or higher. Some spells can be cast at higher levels for increased effect. Spells require verbal, somatic, or material components as specified.</p>
        
        <p><strong>Concentration:</strong> Some spells require concentration to maintain their effects. If you lose concentration, the spell ends. You lose concentration when you cast another concentration spell, take damage, or are incapacitated.</p>
    </body>
    </html>
    """
    
    # Write the HTML files
    test_files = {
        "dnd_character_creation.html": dnd_content,
        "combat_mechanics.html": combat_content,  
        "spell_compendium.html": spell_content
    }
    
    for filename, content in test_files.items():
        file_path = fixtures_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created: {file_path}")
    
    print(f"\nGenerated {len(test_files)} HTML test fixtures in {fixtures_dir}/")
    print("These can be converted to PDFs for testing the ingestion pipeline.")
    
    return fixtures_dir

if __name__ == "__main__":
    create_test_pdf_content()