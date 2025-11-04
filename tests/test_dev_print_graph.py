
def test_dev_print_graph_imports_and_runs():
    from src import dev_print_graph

    # Just make sure it runs without throwing
    # This will build the graph and print nodes/edges
    dev_print_graph.main()
