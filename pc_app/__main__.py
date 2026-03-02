"""
Allow running as: python -m pc_app

  python -m pc_app           → GUI (default)
  python -m pc_app --cli     → CLI mode (headless / original interface)
  python -m pc_app --debug   → Debug visualization tool
"""
import sys

if "--debug" in sys.argv:
    sys.argv.remove("--debug")
    from pc_app.src.debug_tool import main
elif "--cli" in sys.argv:
    sys.argv.remove("--cli")
    from pc_app.src.main import main
else:
    from pc_app.src.gui import main

main()
