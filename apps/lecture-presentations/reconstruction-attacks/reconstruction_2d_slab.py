"""Deferred Marimo/WASM entrypoint for the 2-D feasible-region slab widget.

The shipped web lecture currently embeds the external-app at
``apps/reconstruction-2d-slab/index.html``. Keep this file as the future
Python/WASM route once a hosted ``libdpy`` wheel exists.

Import-only: the entire widget is defined in libdpy. This file just installs libdpy (browser =
hosted wheel via micropip, never git+; v4 §1.1) and invokes it. No domain logic lives here.

Exported to WASM in CI:
    marimo export html-wasm reconstruction_2d_slab.py -o _site/.../apps/reconstruction-2d-slab --mode run
"""

import marimo

app = marimo.App()


@app.cell
def _():
    import micropip  # noqa: F401  (browser only)
    # await micropip.install("<hosted libdpy wheel URL>")   # hosted wheel (v4 §1.1)
    from libdpy.assignment_specific.reconstruction.reconstruction_lecture_visualization import (
        Reconstruction2DSlabPlot,
    )
    Reconstruction2DSlabPlot().show()
    return


if __name__ == "__main__":
    app.run()
