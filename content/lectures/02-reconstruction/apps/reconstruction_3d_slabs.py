"""Deferred Marimo/WASM entrypoint for the 3-D feasible-region slabs widget.

The shipped web lecture currently embeds the browser-native app at
``apps/reconstruction-3d-slabs/index.html``. Keep this file as the future
Python/WASM route once a hosted ``libdpy`` wheel exists.

Import-only: the entire widget is defined in libdpy. This file just installs libdpy (browser =
hosted wheel via micropip, never git+; v4 §1.1) and invokes it. No domain logic lives here.

Exported to WASM in CI:
    marimo export html-wasm reconstruction_3d_slabs.py -o _site/.../apps/reconstruction-3d-slabs --mode run
"""

import marimo

app = marimo.App()


@app.cell
def _():
    import micropip  # noqa: F401  (browser only)
    # await micropip.install("<hosted libdpy wheel URL>")   # hosted wheel (v4 §1.1)
    from libdpy.assignment_specific.reconstruction.reconstruction_3d_visualization import (
        interactive_3d_slabs,
    )
    interactive_3d_slabs()
    return


if __name__ == "__main__":
    app.run()
