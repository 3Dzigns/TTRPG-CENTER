#!/usr/bin/env python3
"""
Create actual PDF test fixtures for Phase 1 ingestion pipeline validation.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from pathlib import Path

def create_dnd_character_pdf():
    """Create D&D Character Creation Guide PDF"""
    filename = Path("test_fixtures/dnd_character_creation.pdf")
    doc = SimpleDocTemplate(str(filename), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.darkred)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, textColor=colors.darkblue)
    
    content = []
    
    # Title
    content.append(Paragraph("Dungeons & Dragons Character Creation Guide", title_style))
    content.append(Spacer(1, 24))
    
    # Chapter 1
    content.append(Paragraph("Chapter 1: Race Selection", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Choosing your character's race is the first major decision in D&D character creation. Each race provides specific ability score increases, traits, and cultural background that shape your character's identity and capabilities.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    content.append(Paragraph("<b>Human:</b> Versatile and adaptable, humans receive a +1 to all ability scores. They are excellent for any class and provide flexibility in character builds.", styles['Normal']))
    content.append(Spacer(1, 6))
    
    content.append(Paragraph("<b>Elf:</b> Graceful and long-lived, elves receive a +2 to Dexterity. They have keen senses, fey ancestry, and proficiency with certain weapons.", styles['Normal']))
    content.append(Spacer(1, 18))
    
    # Chapter 2  
    content.append(Paragraph("Chapter 2: Class Features", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Your character class determines your core abilities, hit points, proficiencies, and how you contribute to your adventuring party.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    content.append(Paragraph("<b>Fighter:</b> Masters of martial combat, fighters can use all armor and weapons. They gain Second Wind for self-healing and Action Surge for additional actions.", styles['Normal']))
    content.append(Spacer(1, 6))
    
    content.append(Paragraph("<b>Wizard:</b> Scholars of arcane magic, wizards cast spells using their Intelligence. They prepare spells from a spellbook and can learn new spells as they advance.", styles['Normal']))
    content.append(Spacer(1, 18))
    
    # Chapter 3
    content.append(Paragraph("Chapter 3: Ability Scores", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Six ability scores define your character's basic capabilities: Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    content.append(Paragraph("Roll 4d6, drop the lowest die, and record the total. Repeat this process six times to generate your ability scores, then assign them to the six abilities as desired.", styles['Normal']))
    
    doc.build(content)
    return filename

def create_combat_mechanics_pdf():
    """Create Combat Mechanics Reference PDF"""
    filename = Path("test_fixtures/combat_mechanics.pdf")
    doc = SimpleDocTemplate(str(filename), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.darkslategray)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, textColor=colors.saddlebrown)
    
    content = []
    
    # Title
    content.append(Paragraph("TTRPG Combat Mechanics Reference", title_style))
    content.append(Spacer(1, 24))
    
    # Initiative
    content.append(Paragraph("Initiative and Turn Order", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("At the start of combat, each participant rolls initiative by making a Dexterity check. The DM ranks all combatants in order from highest to lowest initiative result. This is the order in which they act during each round.", styles['Normal']))
    content.append(Spacer(1, 18))
    
    # Actions
    content.append(Paragraph("Actions in Combat", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("On your turn, you can move and take one action. You can also take one bonus action and any number of free actions.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    # Action table
    action_data = [
        ['Action Type', 'Description', 'Examples'],
        ['Action', 'The main thing you do on your turn', 'Attack, Cast a Spell, Dash, Help'],
        ['Bonus Action', 'Quick additional activity', 'Off-hand attack, certain spells'],
        ['Reaction', 'Response to a trigger', 'Opportunity attack, counterspell']
    ]
    
    action_table = Table(action_data, colWidths=[1.5*inch, 2*inch, 2.5*inch])
    action_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    
    content.append(action_table)
    content.append(Spacer(1, 18))
    
    # Attacks
    content.append(Paragraph("Attack Rolls", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("To make an attack roll, roll a d20 and add your ability modifier and proficiency bonus (if applicable). If the total equals or exceeds the target's Armor Class (AC), the attack hits.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    content.append(Paragraph("<b>Critical Hits:</b> When you roll a natural 20 on an attack roll, you score a critical hit. Roll all damage dice twice and add your normal damage modifiers.", styles['Normal']))
    content.append(Spacer(1, 18))
    
    # Damage
    content.append(Paragraph("Damage and Hit Points", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("When you take damage, you lose hit points. If you reach 0 hit points, you fall unconscious and must make death saving throws on subsequent turns.", styles['Normal']))
    
    doc.build(content)
    return filename

def create_spell_compendium_pdf():
    """Create Spell Compendium PDF"""
    filename = Path("test_fixtures/spell_compendium.pdf")
    doc = SimpleDocTemplate(str(filename), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.darkviolet)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, textColor=colors.darkred)
    spell_style = ParagraphStyle('SpellName', parent=styles['Normal'], fontSize=12, textColor=colors.darkviolet, leftIndent=12, spaceBefore=12)
    
    content = []
    
    # Title
    content.append(Paragraph("Arcane Spell Compendium", title_style))
    content.append(Spacer(1, 24))
    
    # 1st Level Spells
    content.append(Paragraph("1st Level Spells", heading_style))
    content.append(Spacer(1, 12))
    
    # Magic Missile
    content.append(Paragraph("<b>Magic Missile</b>", spell_style))
    content.append(Paragraph("<b>Casting Time:</b> 1 action<br/><b>Range:</b> 120 feet<br/><b>Components:</b> V, S<br/><b>Duration:</b> Instantaneous", styles['Normal']))
    content.append(Paragraph("You create three glowing darts of magical force. Each dart hits a creature of your choice within range, dealing 1d4 + 1 force damage. The darts strike simultaneously.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    # Shield
    content.append(Paragraph("<b>Shield</b>", spell_style))
    content.append(Paragraph("<b>Casting Time:</b> 1 reaction<br/><b>Range:</b> Self<br/><b>Components:</b> V, S<br/><b>Duration:</b> 1 round", styles['Normal']))
    content.append(Paragraph("An invisible barrier of magical force appears around you, granting a +5 bonus to AC and immunity to magic missile spells.", styles['Normal']))
    content.append(Spacer(1, 18))
    
    # 3rd Level Spells (Fireball is actually 3rd level)
    content.append(Paragraph("3rd Level Spells", heading_style))
    content.append(Spacer(1, 12))
    
    # Fireball
    content.append(Paragraph("<b>Fireball</b>", spell_style))
    content.append(Paragraph("<b>Casting Time:</b> 1 action<br/><b>Range:</b> 150 feet<br/><b>Components:</b> V, S, M (a tiny ball of bat guano and sulfur)<br/><b>Duration:</b> Instantaneous", styles['Normal']))
    content.append(Paragraph("A bright streak flashes from your pointing finger to a point within range and blossoms into an explosion of flame. Each creature in a 20-foot-radius sphere must make a Dexterity saving throw, taking 8d6 fire damage on failure or half on success.", styles['Normal']))
    content.append(Spacer(1, 18))
    
    # Spellcasting Mechanics
    content.append(Paragraph("Spellcasting Mechanics", heading_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph("To cast a spell, you must expend a spell slot of the spell's level or higher. Some spells can be cast at higher levels for increased effect. Spells require verbal, somatic, or material components as specified.", styles['Normal']))
    content.append(Spacer(1, 12))
    
    content.append(Paragraph("<b>Concentration:</b> Some spells require concentration to maintain their effects. If you lose concentration, the spell ends. You lose concentration when you cast another concentration spell, take damage, or are incapacitated.", styles['Normal']))
    
    doc.build(content)
    return filename

def main():
    """Generate all test PDF fixtures"""
    print("Creating PDF test fixtures...")
    
    # Create test_fixtures directory
    Path("test_fixtures").mkdir(exist_ok=True)
    
    # Generate PDFs
    files_created = []
    
    try:
        file1 = create_dnd_character_pdf()
        files_created.append(file1)
        print(f"Created: {file1}")
        
        file2 = create_combat_mechanics_pdf()
        files_created.append(file2)
        print(f"Created: {file2}")
        
        file3 = create_spell_compendium_pdf()
        files_created.append(file3)
        print(f"Created: {file3}")
        
        print(f"\nSuccessfully generated {len(files_created)} PDF test fixtures!")
        print("These PDFs contain realistic TTRPG content for testing the ingestion pipeline.")
        
    except Exception as e:
        print(f"Error creating PDFs: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()