# UNDECEMBER Damage Calculator

**Version:** `v0.14.40`

A standalone Python/Tkinter calculator for reconstructing and analyzing
damage values in **UNDECEMBER**.

The calculator is designed around a specific principle:

> **The in-game skill tooltip is the authoritative starting point
> whenever an actual tooltip value is available.**

The calculation pipeline is therefore split into stages:

1.  Character Attack/Spell base
2.  Main damage tooltip by damage type
3.  Tag modifiers
4.  Additional damage packets
5.  Double / Triple / Critical post-tooltip modifiers

The application also contains a playable Zodiac/Constellation view and
an interactive constellation-node editor.


## Project Status

I have reached the point where I am simply tired of figuring out and reverse-engineering every formula on my own.

There are still many things about UNDECEMBER's damage calculations that need to be studied and verified. Instead of keeping this project private or stopping the work entirely, I am making it publicly available for anyone interested in continuing the research.

**I give full permission to use my work as a basis for further research, testing, modification, and development of the damage calculator.**

You are free to:
- study and analyze the existing formulas and implementation;
- use my test results and findings;
- modify and improve the calculator;
- continue reverse-engineering UNDECEMBER's damage mechanics;
- use the code as a foundation for a new or different calculator;
- share and publish further findings based on this work.

If you can figure out formulas that I couldn't, correct something I got wrong, or take the calculator further than I did, **please do it**.

The goal is ultimately to understand how the game's damage calculation actually works, and I am happy for this project to be used by anyone who wants to continue that work.

------------------------------------------------------------------------

------------------------------------------------------------------------

## Features

### Damage calculator

The calculator supports:

-   Attack or Spell as the damage source
-   Physical damage
-   Fire damage
-   Cold damage
-   Lightning damage
-   Poison damage
-   Chaos damage
-   Generic Damage Increase / Amplification
-   Attack Damage Increase / Amplification
-   Spell Damage Increase / Amplification
-   per-element Increase / Amplification
-   tag modifiers:
    -   Area
    -   Projectile
    -   Melee
    -   Strike
-   multiple independent modifier sources through `+` buttons
-   direct entry of the actual in-game tooltip
-   up to 5 additional damage packets
-   Double damage
-   Triple damage
-   Critical damage
-   Critical chance
-   Zodiac/Constellation bonuses
-   detailed calculation output showing intermediate stages

The UI is divided into:

-   **Calculator**
-   **Constellations**
-   **Node Editor**

------------------------------------------------------------------------

# 1. Basic terminology

## Increase

`Increase %` sources are **additive within the same modifier pool**.

For example:

``` text
+20% Increase
+15% Increase
+10% Increase
```

becomes:

``` text
+45% Increase
```

The resulting multiplier is:

``` text
1 + Increase / 100
```

So `+45% Increase` gives:

``` text
×1.45
```

------------------------------------------------------------------------

## Amplification

`Amplification %` sources are **multiplicative**.

For independent Amplification sources:

``` text
+10%
+20%
+30%
```

the factor is:

``` text
(1 + 10/100)
× (1 + 20/100)
× (1 + 30/100)
```

or:

``` text
1.10 × 1.20 × 1.30
= 1.716
```

The resulting amplification is therefore `+71.6%`, not `+60%`.

This rule is implemented by the calculator's `multi_amp_factor()`
function.

------------------------------------------------------------------------

## Flat damage

Flat damage is added to the relevant base damage before the Increase/Amp
stage.

For a component:

``` text
Base
+ Flat Damage
+ Skill Flat
```

forms the pre-Increase value.

------------------------------------------------------------------------

## Skill Damage %

`Skill Damage %` is applied as a multiplier:

``` text
Skill / 100
```

For example:

``` text
150% Skill Damage
```

means:

``` text
×1.50
```

------------------------------------------------------------------------

## Tooltip

The tooltip is the actual damage range displayed by the game for a
skill/damage type.

The calculator supports **direct tooltip input**.

When a tooltip MIN/MAX value is entered, it replaces the calculated
component **at the main-tooltip stage**.

The calculated value is still retained internally and shown in the
diagnostic output for comparison.

All later stages continue to operate on the entered tooltip:

``` text
Entered Tooltip
→ Tags
→ Additional Damage
→ Double / Triple
→ Critical
```

This is the intended mode for comparing the calculator against real
in-game tooltip values.

------------------------------------------------------------------------

# 2. Character damage stage

The calculator first constructs the Attack or Spell base.

For Attack:

``` text
AttackFactor =
    (1 + (Σ Attack Increase + Zodiac Attack Increase) / 100)
    × Π(1 + Attack Amplification / 100)
    × (1 + Zodiac Attack Amplification / 100)
```

Then:

``` text
AttackMin = AttackBaseMin × AttackFactor
AttackMax = AttackBaseMax × AttackFactor
```

For Spell:

``` text
SpellFactor =
    (1 + (Σ Spell Increase + Zodiac Spell Increase) / 100)
    × Π(1 + Spell Amplification / 100)
    × (1 + Zodiac Spell Amplification / 100)
```

Then:

``` text
SpellMin = SpellBaseMin × SpellFactor
SpellMax = SpellBaseMax × SpellFactor
```

The selected source determines which range becomes the damage base:

``` text
Source = Attack → Attack range
Source = Spell  → Spell range
```

------------------------------------------------------------------------

# 3. Main tooltip formula

Each damage component is calculated independently.

Supported components:

-   Physical
-   Fire
-   Cold
-   Lightning
-   Poison
-   Chaos

The core component formula is:

``` text
MinDamage =
    (BaseMin + FlatMin + SkillFlat)
    × (1 + EffectiveIncrease / 100)
    × EffectiveAmplification
    × (SkillDamage / 100)
    × KMin
```

and:

``` text
MaxDamage =
    (BaseMax + FlatMax + SkillFlat)
    × (1 + EffectiveIncrease / 100)
    × EffectiveAmplification
    × (SkillDamage / 100)
    × KMax
```

Where:

-   `BaseMin/BaseMax` = calculated Attack or Spell base
-   `FlatMin/FlatMax` = flat damage of the component
-   `SkillFlat` = skill-specific flat contribution
-   `EffectiveIncrease` = all applicable Increase sources for that
    component
-   `EffectiveAmplification` = product of all applicable Amplification
    sources
-   `SkillDamage` = Skill Damage %
-   `KMin/KMax` = internal empirical calibration coefficient

Generic Damage modifiers are merged into the corresponding component
exactly once.

They are **not** applied again to the already summed subtotal.

------------------------------------------------------------------------

# 4. Damage-type modifiers

Each damage type has its own Increase and Amplification pool.

For example, Physical uses:

``` text
Physical Increase
Physical Amplification
```

Fire uses:

``` text
Fire Increase
Fire Amplification
```

and so on.

Generic Damage is common to the applicable component:

``` text
EffectiveIncrease =
    ComponentIncrease
    + GenericIncrease
    + ZodiacComponentIncrease
```

and:

``` text
EffectiveAmplification =
    ComponentAmplification
    × GenericAmplification
    × ZodiacComponentAmplification
```

------------------------------------------------------------------------

# 5. Internal K coefficients

The calculator contains hidden calibration coefficients.

They are intentionally not exposed as normal user inputs because they
are internal parameters of the current empirical model.

Current defaults include:

### Main damage

Physical:

``` text
KMin = 0.80014461
KMax = 0.84762186
```

Elemental:

``` text
KMin = 0.74262000
KMax = 0.74262000
```

### Tag coefficients

Area:

``` text
KMin = 27.22901910
KMax = 26.06424224
```

Projectile:

``` text
KMin = 27.26937656
KMax = 26.08843876
```

Melee:

``` text
KMin = 27.28406285
KMax = 26.09530493
```

Strike:

``` text
KMin = 27.22901910
KMax = 26.06424224
```

These values are **empirical calibration constants**, not claims that
UNDECEMBER exposes these coefficients directly.

They exist because the calculator is intended to reproduce observed
in-game values using the current tested model.

------------------------------------------------------------------------

# 6. Direct tooltip mode

Direct tooltip input is especially important for validation.

For each damage type the user can enter:

``` text
MIN
MAX
```

Example:

``` text
Physical Tooltip:
1000 – 1200
```

When a non-zero tooltip range is entered, that range replaces the
calculated Physical component at the tooltip stage.

The calculator output still reports the reconstructed value:

``` text
Physical 1000 – 1200
| ENTERED TOOLTIP
| calculation was  ...
```

This allows direct comparison between:

-   reconstructed model
-   real in-game tooltip

without forcing the upstream reconstruction to be correct for every
skill.

------------------------------------------------------------------------

# 7. Tag modifiers

Supported tags:

-   Area
-   Projectile
-   Melee
-   Strike

Each tag can be enabled/disabled.

Each tag has:

``` text
Increase %
Amplification %
```

and each modifier can have multiple independent sources.

For example:

``` text
Area Increase:
+5%
+8%
+12%
```

becomes:

``` text
+25%
```

while:

``` text
Area Amplification:
+3%
+4%
```

becomes:

``` text
1.03 × 1.04
= 1.0712
```

or:

``` text
×1.0712
```

------------------------------------------------------------------------

## Important tag rule

Multiple active tags do **not** compound sequentially.

For example:

``` text
Tooltip
→ Area
→ Projectile
```

does not mean:

``` text
Tooltip × Area
→ result × Projectile
```

Instead, every active tag modifier is calculated from the **same pre-tag
tooltip**.

This prevents one tag from incorrectly becoming the base of the next
tag.

The current implementation uses a common tag-amplification pool.

The Increase side uses the corresponding empirical K model.

The Amplification side is explicitly marked in the source as an
experimental empirical model.

------------------------------------------------------------------------

# 8. Tag Increase model

For a tag Increase contribution:

``` text
TagBonusMin =
    BaseMin × TagKMin × (TagIncrease / 100)
```

``` text
TagBonusMax =
    BaseMax × TagKMax × (TagIncrease / 100)
```

All applicable tag Increase contributions are then added to the
tag-adjusted tooltip.

------------------------------------------------------------------------

# 9. Tag Amplification model

All active tag Amplification sources are accumulated into one common
multiplicative factor.

Conceptually:

``` text
TagAmpFactor =
    Π(1 + TagAmplification / 100)
```

The current implementation applies this factor to a common pre-K pool
consisting of:

``` text
pre-tag tooltip
+
raw tag-Increase portions
```

The implementation comments explicitly identify this as the current
empirical model rather than a universally proven game formula.

------------------------------------------------------------------------

# 10. Additional damage packets

The calculator supports up to **5 additional damage packets**.

Each packet has:

``` text
On
Source
Target
%
```

Supported Source/Target damage types:

-   Physical
-   Cold
-   Lightning
-   Poison
-   Fire

The packet is calculated from the **average damage of its source
component**:

``` text
AverageSource =
    (SourceMin + SourceMax) / 2
```

Then:

``` text
ExtraDamage =
    AverageSource × PacketPercent / 100
```

This creates a flat packet:

``` text
ExtraDamage – ExtraDamage
```

------------------------------------------------------------------------

## Same-element packet

If:

``` text
Source == Target
```

the packet is merged into that damage type.

It therefore contributes to the main tooltip.

------------------------------------------------------------------------

## Cross-element packet

If:

``` text
Source != Target
```

the packet remains separate.

It is reported as:

``` text
SEPARATE EXTRA PACKETS
```

and added to the final hit after the main tooltip.

------------------------------------------------------------------------

## Current 17% packet model

The current calculator contains a specifically tested model for the 17%
additional-damage packet.

It uses:

``` text
17% × average damage of the source component
```

and does **not** reapply the target's Increase/Amplification to that
packet.

This is a verified working model currently encoded in the calculator,
but it should be treated as an empirical rule rather than a general
game-system claim.

------------------------------------------------------------------------

# 11. Main tooltip and total hit

After the tag stage:

``` text
MAIN TOOLTIP
```

represents the tag-adjusted main damage.

Same-element additional packets are then merged into it.

Cross-element packets remain separate.

Finally:

``` text
TOTAL HIT =
    MAIN TOOLTIP
    + SEPARATE EXTRA PACKETS
```

The calculator reports all three concepts independently.

------------------------------------------------------------------------

# 12. Double Damage

Double is applied **after the tooltip and additional-damage stages**.

For:

``` text
Double Maximum Damage Increase = D%
```

the multiplier is:

``` text
DoubleMultiplier = 1 + D / 100
```

Therefore:

``` text
DoubleMin = TotalHitMin × DoubleMultiplier
DoubleMax = TotalHitMax × DoubleMultiplier
```

Example:

``` text
D = 50%
```

gives:

``` text
×1.50
```

------------------------------------------------------------------------

# 13. Triple Damage

Triple is also applied after the tooltip and additional-damage stages.

For:

``` text
Triple Maximum Damage Increase = T%
```

the multiplier is:

``` text
TripleMultiplier = 1 + T / 100
```

Therefore:

``` text
TripleMin = TotalHitMin × TripleMultiplier
TripleMax = TotalHitMax × TripleMultiplier
```

------------------------------------------------------------------------

## Maximum Damage Zodiac node

The Zodiac editor supports:

``` text
Maximum Damage Increase
```

A node with value `X%` contributes:

``` text
Double +X%
Triple +2X%
```

So a:

``` text
+5% Maximum Damage Increase
```

node becomes:

``` text
Double +5%
Triple +10%
```

inside the calculator.

------------------------------------------------------------------------

# 14. Critical damage

The calculator uses a base critical multiplier of:

``` text
1.5
```

Additional Critical Damage is added to that multiplier.

For:

``` text
Critical Damage Increase = C%
```

the multiplier is:

``` text
CriticalMultiplier =
    1.5 + C / 100
```

Therefore:

``` text
CriticalNormal =
    TotalHit × CriticalMultiplier
```

Example:

``` text
Critical Damage = +50%
```

gives:

``` text
1.5 + 0.50
= 2.0
```

or:

``` text
×2.00
```

------------------------------------------------------------------------

# 15. Double Critical / Triple Critical

The post-tooltip modifiers multiply independently.

Double Critical:

``` text
DoubleCritical =
    TotalHit
    × DoubleMultiplier
    × CriticalMultiplier
```

Triple Critical:

``` text
TripleCritical =
    TotalHit
    × TripleMultiplier
    × CriticalMultiplier
```

The calculator therefore reports:

``` text
Normal
Double
Triple
Critical Normal
Double Critical
Triple Critical
```

------------------------------------------------------------------------

# 16. Critical chance and expected damage

Critical Chance does not alter the displayed critical hit range.

It is used only for the expected-damage calculation.

The expected multiplier is:

``` text
ExpectedFactor =
    1 + CriticalChance / 100 × (CriticalMultiplier - 1)
```

So:

``` text
ExpectedDamage =
    NormalDamage × ExpectedFactor
```

This treats critical chance as a probability-weighted increase over
normal damage.

------------------------------------------------------------------------

# 17. Zodiac / Constellations

The calculator contains a working Zodiac interface.

It supports:

-   9 constellations
-   multiple branches per constellation
-   root nodes
-   linked nodes
-   active/inactive node states
-   automatic availability checking
-   automatic removal of children whose prerequisite is removed
-   automatic aggregation of active bonuses
-   immediate propagation of Zodiac bonuses into the damage calculator

A root node is immediately available.

A non-root node becomes available when at least one linked node is
active.

Links are treated as bidirectional for the working constellation view.

------------------------------------------------------------------------

## Zodiac modifier types

The current editor supports:

``` text
Attack Damage Increase
Attack Damage Amplification

Spell Damage Increase
Spell Damage Amplification

Physical Damage Increase
Physical Damage Amplification

Elemental Damage Increase
Elemental Damage Amplification

Fire Damage Increase
Fire Damage Amplification

Cold Damage Increase
Cold Damage Amplification

Lightning Damage Increase
Lightning Damage Amplification

Poison Damage Increase
Poison Damage Amplification

Projectile Damage Increase
Projectile Damage Amplification

Melee Damage Increase
Melee Damage Amplification

Area Damage Increase
Area Damage Amplification

Strike Damage Increase
Strike Damage Amplification

Double Maximum Damage Increase
Triple Maximum Damage Increase

Critical Damage Increase

Generic Damage Increase
Generic Damage Amplification
```

------------------------------------------------------------------------

# 18. Elemental Zodiac modifiers

A Zodiac:

``` text
Elemental Damage Increase
```

is applied independently to:

-   Fire
-   Cold
-   Lightning
-   Poison

So:

``` text
+10% Elemental Damage Increase
```

adds:

``` text
+10% Fire Increase
+10% Cold Increase
+10% Lightning Increase
+10% Poison Increase
```

Elemental Amplification is handled multiplicatively in the same way.

------------------------------------------------------------------------

# 19. Constellation editor

The application includes an interactive node-layout editor.

It can:

-   move nodes with the mouse
-   create/delete branches
-   create/delete nodes
-   link nodes
-   unlink nodes
-   edit node parameters
-   mark nodes as roots
-   save JSON
-   load JSON
-   export JSON
-   use custom background artwork
-   use custom node artwork
-   use custom branch artwork

Node positions are stored as relative coordinates:

``` text
0.0 ... 1.0
```

for both X and Y.

This makes the layout independent of the window resolution.

------------------------------------------------------------------------

# 20. JSON layout

The editor uses:

``` text
undecember_constellation_layout_v1
```

as its layout format identifier.

A node can contain fields such as:

``` json
{
  "id": "example-node",
  "x": 0.5,
  "y": 0.5,
  "name": "Physical Damage: +10%",
  "effect": "Physical Damage Increase",
  "value": 10,
  "type": "node",
  "parent_id": null,
  "links": [],
  "root": true
}
```

The editor validates:

-   constellation identifiers
-   branch identifiers
-   node lists
-   finite coordinates
-   coordinates in the `0..1` range
-   numeric node values

Older parent-only layouts are normalized into the newer
bidirectional-link representation.

------------------------------------------------------------------------

# 21. Custom editor artwork

The editor can load three optional images:

``` text
assets/background.png
assets/node.png
assets/branch.png
```

If Pillow is installed, supported source images can be converted to PNG
automatically.

If Pillow is unavailable, PNG is required.

Custom artwork is stored next to the application so it survives a
restart.

------------------------------------------------------------------------

# 22. Input sources and multiple modifiers

Many modifier fields support multiple independent sources.

The `+` button adds another source.

For Increase:

``` text
source 1 + source 2 + source 3
```

For Amplification:

``` text
(1 + source 1/100)
× (1 + source 2/100)
× (1 + source 3/100)
```

Removing a source does not renumber the remaining data internally; the
removed source is simply zeroed.

------------------------------------------------------------------------

# 23. Weapon Range

**Weapon Range is completely excluded from the calculation.**

It is not used as:

-   a damage multiplier
-   a range multiplier
-   a hidden coefficient
-   an additional damage component

It does not enter any formula in the current calculator.

------------------------------------------------------------------------

# 24. Calculation pipeline

The complete current pipeline is:

``` text
                 ┌─────────────────────┐
                 │ Character Base      │
                 │ Attack / Spell      │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Damage Components   │
                 │ Physical / Element  │
                 │ Increase + Amp      │
                 │ Skill % + Flat      │
                 │ K coefficients      │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Direct Tooltip      │
                 │ if supplied         │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Tag Modifiers       │
                 │ Area / Projectile   │
                 │ Melee / Strike      │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Additional Packets  │
                 │ up to 5             │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ TOTAL HIT           │
                 └──────────┬──────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           Normal         Double        Triple
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                     Critical multiplier
                            │
                            ▼
                 Critical / Double Crit
                 / Triple Crit
```

------------------------------------------------------------------------

# 25. Important model limitations

This project is an **empirical damage model**.

It is not intended to claim that every internal coefficient or
interaction has been officially documented by the game developer.

In particular:

-   K coefficients are calibration constants.
-   Tag Amplification currently uses an empirical common-pool model.
-   The 17% additional-damage packet uses a specifically tested
    empirical model.
-   Direct tooltip mode is the preferred validation mechanism when the
    game provides the actual tooltip.
-   The calculator does not attempt to reconstruct every possible hidden
    game mechanic.

The purpose is reproducibility and comparison with observed in-game
numbers.

------------------------------------------------------------------------

# 26. Validation philosophy

The calculator should be validated against controlled in-game tests.

The most useful tests are:

1.  Disable all unnecessary modifiers.
2.  Record the actual tooltip.
3.  Enter the tooltip directly.
4.  Enable exactly one modifier.
5.  Compare the calculator delta with the in-game delta.
6.  Repeat for Increase and Amplification separately.
7.  Test Double / Triple / Critical separately.
8.  Test tag modifiers independently.
9.  Test additional packets independently.

This avoids accidentally fitting one modifier using another modifier's
effect.

------------------------------------------------------------------------

# 27. Running the calculator

The application is written in Python and uses Tkinter.

Basic launch:

``` bash
python calculator.py
```

The exact filename depends on how the repository is packaged.

The program requires:

-   Python 3
-   Tkinter

Pillow is optional and is used for custom editor artwork.

------------------------------------------------------------------------

# 28. Project structure

A recommended repository structure is:

``` text
UNDECEMBER-Damage-Calculator/
│
├── calculator.py
├── README.md
├── LICENSE
├── assets/
│   ├── background.png
│   ├── node.png
│   └── branch.png
│
└── data/
    └── constellations.json
```

The current Python source already contains a built-in constellation
layout, so external constellation JSON is optional.

------------------------------------------------------------------------

# 29. Current version

``` text
UNDECEMBER Damage Calculator v0.14.40
```

This README describes the calculation behavior implemented in that
version.

The source itself is the authoritative reference if the README and
implementation ever diverge.

------------------------------------------------------------------------

## License

Add the license appropriate for the repository before publishing.

If this project is based on reverse-engineering or community testing of
UNDECEMBER mechanics, make it clear that it is an unofficial community
tool and is not affiliated with or endorsed by the game's
publisher/developer.
