def test_sanity_imports():
    import src.sanity as mod
    # if sanity has a main() that only reads env, just call it guarded
    if hasattr(mod, "main"):
        mod.main()
