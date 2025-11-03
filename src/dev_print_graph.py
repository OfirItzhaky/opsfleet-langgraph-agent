from src.graph import build_graph


def main() -> None:
    app = build_graph()
    print("Graph compiled successfully.")
    g = app.get_graph()  # get the underlying graph object
    print("Nodes:", list(g.nodes))
    print("Edges:")
    for edge in g.edges:
        print(" ", edge)


if __name__ == "__main__":
    main()
