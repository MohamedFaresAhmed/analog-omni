# Example netlists

Four amplifier netlists with generic device names. They are not tied to any PDK.

| File | Circuit | Syntax |
|---|---|---|
| `5T_OTA_Netlist.txt` | Five-transistor OTA with bias current, inputs, supply and load capacitor | Spectre |
| `Two_Stage_Miller_Netlist.txt` | Two-stage Miller OTA with compensation capacitor and nulling resistor; devices only, no sources | Spectre |
| `Folded_Cascode_Netlist.txt` | Folded-cascode OTA core; devices only, no sources | Spectre |
| `CS_Amp.txt` | Common-source amplifier with a small-signal MOS model (`gm`, `gb`, `go` and five capacitances) | SLiCAP-style |

In the Spectre files, `nmos` and `pmos` are placeholder model names: map them to the models of your PDK before simulating. Device sizes are either symbols (`W1`, `L1`, ...) or example values.

`CS_Amp.txt` uses SLiCAP-style syntax, not Spectre: a title line, elements written as `name nodes type param={value}`, and `.end`. Its MOS device `M1` (nodes drain, gate, source, bulk) has no model; it is given by its small-signal parameters: `gm`, `gb` (bulk transconductance), `go = 1/ro`, and the capacitances `cgs`, `cdg`, `cgb`, `cdb`, `csb`. It is meant for small-signal analysis and does not run in ngspice or Spectre as written.
