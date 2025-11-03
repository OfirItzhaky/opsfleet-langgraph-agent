from src.graph import build_graph


def test_graph_compiles_and_has_nodes():
    app = build_graph()
    g = app.get_graph()

    # nodes present
    assert "intent" in g.nodes
    assert "plan" in g.nodes
    assert "respond" in g.nodes
    assert "__end__" in g.nodes

    # edges present (check by source/target)
    edges = {(e.source, e.target) for e in g.edges}
    assert ("intent", "plan") in edges
    assert ("plan", "sqlgen") in edges
    assert ("sqlgen", "exec") in edges
    assert ("exec", "results") in edges
    assert ("results", "insight") in edges
    assert ("insight", "respond") in edges
    assert ("respond", "__end__") in edges
