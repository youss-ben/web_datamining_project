# swrl_reasoning.py — SWRL Rules on family.owl and Artemis KB
# Uses OWLReady2 with manual Python-based rule application (no Java required).
from owlready2 import *
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
KG_DIR = ROOT / "kg_artifacts"

# ============ PART 1: family.owl ============
print("=" * 55)
print("  PART 1: SWRL on family.owl")
print("=" * 55)

family_path = str(DATA_DIR / "family.owl")
onto = get_ontology(f"file://{family_path}").load()

with onto:
    # Define the SWRL rule (for documentation purposes)
    rule = Imp()
    rule.set_as_rule("Person(?p), hasAge(?p, ?a), greaterThan(?a, 65) -> oldPerson(?p)")
    print(f"\nSWRL Rule: {rule}")
    print("  English: If a Person has age > 65, classify them as oldPerson.\n")

# Try Java-based reasoner first; fall back to manual Python application
print("Running reasoner...")
reasoner_worked = False
try:
    sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
    reasoner_worked = True
    print("Pellet reasoner completed.\n")
except Exception:
    try:
        sync_reasoner(infer_property_values=True)
        reasoner_worked = True
        print("HermiT reasoner completed.\n")
    except Exception:
        print("  Java not found — applying rules manually in Python.\n")

# Manual rule application (works without Java)
if not reasoner_worked:
    with onto:
        for person in onto.Person.instances():
            age = person.hasAge
            if age is not None and age > 65:
                person.is_a.append(onto.oldPerson)

print("--- Inferred oldPerson Instances ---")
count = 0
for person in onto.Person.instances():
    is_old = onto.oldPerson in person.is_a or isinstance(person, onto.oldPerson)
    if not is_old and person.hasAge and person.hasAge > 65:
        is_old = True
    if is_old:
        print(f"  ✓ {person.name} (age={person.hasAge}) → classified as oldPerson")
        count += 1
if count == 0:
    print("  (No oldPerson instances found)")

onto.save(file=str(DATA_DIR / "family_inferred.owl"), format="rdfxml")
print(f"\nSaved to: {DATA_DIR / 'family_inferred.owl'}")

# ============ PART 2: Artemis KB ============
print("\n" + "=" * 55)
print("  PART 2: SWRL on Artemis Domain Ontology")
print("=" * 55)

art = get_ontology("http://example.org/artemis_ontology.owl")
with art:
    class SpaceMission(Thing): pass
    class SpaceAgency(Thing): pass
    class LaunchVehicle(Thing): pass
    class CrewMember(Thing): pass

    class operatedBy(ObjectProperty): domain=[SpaceMission]; range=[SpaceAgency]
    class usesVehicle(ObjectProperty): domain=[SpaceMission]; range=[LaunchVehicle]
    class hasCrew(ObjectProperty): domain=[SpaceMission]; range=[CrewMember]
    class manages(ObjectProperty): domain=[SpaceAgency]; range=[LaunchVehicle]
    class trainsCrewFor(ObjectProperty): domain=[SpaceAgency]; range=[CrewMember]

    nasa = SpaceAgency("NASA"); esa = SpaceAgency("ESA")
    sls = LaunchVehicle("SLS"); orion = LaunchVehicle("Orion")
    starship = LaunchVehicle("Starship_HLS")

    a1 = SpaceMission("Artemis_I"); a1.operatedBy=[nasa]; a1.usesVehicle=[sls,orion]
    a2 = SpaceMission("Artemis_II"); a2.operatedBy=[nasa]; a2.usesVehicle=[sls,orion]
    reid = CrewMember("Reid_Wiseman"); victor = CrewMember("Victor_Glover")
    a2.hasCrew = [reid, victor]
    a3 = SpaceMission("Artemis_III"); a3.operatedBy=[nasa]; a3.usesVehicle=[sls,orion,starship]

    # Define SWRL rules (for documentation)
    r1 = Imp(); r1.set_as_rule("SpaceMission(?m), operatedBy(?m,?a), usesVehicle(?m,?v) -> manages(?a,?v)")
    r2 = Imp(); r2.set_as_rule("SpaceMission(?m), operatedBy(?m,?a), hasCrew(?m,?c) -> trainsCrewFor(?a,?c)")
    print(f"\nRule 1: {r1}")
    print(f"Rule 2: {r2}\n")

# Try Java reasoner; fall back to manual application
print("Running reasoner...")
reasoner_worked = False
try:
    sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
    reasoner_worked = True
    print("Pellet completed.\n")
except Exception:
    try:
        sync_reasoner(infer_property_values=True)
        reasoner_worked = True
        print("HermiT completed.\n")
    except Exception:
        print("  Java not found — applying rules manually in Python.\n")

# Manual rule application
if not reasoner_worked:
    with art:
        for mission in art.SpaceMission.instances():
            for agency in mission.operatedBy:
                # Rule 1: operatedBy + usesVehicle → manages
                for vehicle in mission.usesVehicle:
                    if vehicle not in agency.manages:
                        agency.manages.append(vehicle)
                # Rule 2: operatedBy + hasCrew → trainsCrewFor
                for crew in mission.hasCrew:
                    if crew not in agency.trainsCrewFor:
                        agency.trainsCrewFor.append(crew)

print("--- Inferred 'manages' ---")
for a in art.SpaceAgency.instances():
    for v in a.manages:
        print(f"  ✓ {a.name} manages {v.name}")

print("\n--- Inferred 'trainsCrewFor' ---")
for a in art.SpaceAgency.instances():
    for c in a.trainsCrewFor:
        print(f"  ✓ {a.name} trains {c.name}")

art.save(file=str(KG_DIR / "artemis_domain.owl"), format="rdfxml")
print(f"\nSaved to: {KG_DIR / 'artemis_domain.owl'}")
print("\n" + "=" * 55)
print("  SWRL REASONING COMPLETE")
print("=" * 55)
