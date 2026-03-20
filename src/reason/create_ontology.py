# create_ontology.py — Generate family.owl for SWRL lab exercise
from owlready2 import *
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = ROOT / "data" / "family.owl"

onto = get_ontology("http://example.org/family.owl")
with onto:
    class Person(Thing): pass
    class oldPerson(Person): pass
    class hasAge(DataProperty, FunctionalProperty):
        domain = [Person]; range = [int]

    Person("Thomas", hasAge=25); Person("Alex", hasAge=5)
    Person("Michael", hasAge=69); Person("Peter", hasAge=70)
    Person("Marie", hasAge=30); Person("Sylvie", hasAge=45)
    Person("Tom", hasAge=40); Person("Pedro", hasAge=10)
    Person("Claude", hasAge=5); Person("Chloe", hasAge=18)
    Person("Paul", hasAge=38)

onto.save(file=str(OUTPUT), format="rdfxml")
print(f"Created: {OUTPUT}")
