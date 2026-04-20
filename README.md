# inventree-ipp-plugin

An [InvenTree](https://inventree.org/) `MachineDriver` plugin that lets any IPP-capable
network printer — thermal, laser, or inkjet — act as a label printer inside InvenTree.
It implements the `LabelPrinterBaseDriver` interface from `machine.machine_types`, so
InvenTree manages connection state, status polling, and the print dialog automatically.
The plugin is in production use at [inventree.29c.sh](https://inventree.29c.sh).

---

## Install

### From git (recommended)

Use InvenTree's built-in plugin installer:

1. Open **InvenTree Admin → Plugins → Install Plugin**.
2. Enter the repository URL:
   ```
   https://github.com/jhogendorn/inventree-ipp-plugin
   ```
3. Click **Install**, then restart the InvenTree server.

InvenTree will fetch the package directly from GitHub and register the
`inventree-ipp` entry point automatically.

### Local / development

```bash
git clone https://github.com/jhogendorn/inventree-ipp-plugin
cd inventree-ipp-plugin
uv pip install -e .        # or: pip install -e .
```

Restart the InvenTree server so the plugin is discovered via the
`inventree_plugins` entry point.

---

## InvenTree version compatibility

| Requirement | Value  |
|-------------|--------|
| InvenTree   | ≥ 0.18.0 |
| Python      | ≥ 3.11  |

The minimum InvenTree version (`MIN_VERSION = "0.18.0"`) is enforced at
plugin load time by InvenTree's plugin framework.

---

## Driver

| Field       | Value                    |
|-------------|--------------------------|
| Class       | `IppLabelPrinterDriver`  |
| Interface   | `LabelPrinterBaseDriver` (from `machine.machine_types`) |
| Driver slug | `ipp-label-printer`      |
| Plugin slug | `inventree-ipp`          |

InvenTree discovers the driver via the `inventree_plugins` entry point declared
in `pyproject.toml`:

```toml
[project.entry-points."inventree_plugins"]
inventree-ipp = "inventree_ipp:InvenTreeIppPlugin"
```

The driver polls printer state using IPP `Get-Printer-Attributes` and maps
IPP printer-state values (idle=3, processing=4, stopped=5) to
`MACHINE_STATUS.CONNECTED` / `DISCONNECTED`.

---

## Config example

After installation, register a printer instance in InvenTree:

1. Open **InvenTree Admin → Machine → Add Machine**.
2. Set the **Machine type** to **Label Printer**.
3. Set the **Driver** to **IPP Label Printer**.
4. Give the machine a name (e.g. `Office Dymo`).
5. Save, then configure the machine settings:

| Setting       | Required | Description                                        | Example value                      |
|---------------|----------|----------------------------------------------------|-------------------------------------|
| Printer URI   | Yes      | Full IPP URI of the printer                        | `ipp://10.0.4.250:631/ipp/print`    |
| Timeout       | No       | Request timeout in seconds (default: `30`)         | `30`                                |

When printing a label template, an optional **Copies** field (1–99) appears
in the print dialog.

To find your printer's IPP URI, check the printer's web interface or run
`ipptool -tv ipp://<host>/ipp/print get-printer-attributes.test` on the
same network.
