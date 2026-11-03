import networkx as nx

# =====================================================
# SMART TRAFFIC OPTIMIZER GRAPH
# Hadapsar, Pune
# =====================================================

def create_graph():

    G = nx.Graph()

    # =================================================
    # ROAD NODES (REALISTIC INTERSECTIONS)
    # =================================================

    nodes = {

        # ================= HADAPSAR =================

        "Hadapsar_Main": {

            "pos": (
                18.5088,
                73.9250
            )
        },

        "Gadital_Chowk": {

            "pos": (
                18.5015,
                73.9384
            )
        },

        "FatimaNagar_Junction": {

            "pos": (
                18.5097,
                73.9018
            )
        },

        "Magarpatta_Junction": {

            "pos": (
                18.5164,
                73.9320
            )
        },

        "Amanora_Entry": {

            "pos": (
                18.5186,
                73.9365
            )
        }
    }

    # =================================================
    # ADD NODES
    # =================================================

    for node, data in nodes.items():

        G.add_node(

            node,

            pos=data["pos"]
        )

    # =================================================
    # ROAD CONNECTIONS
    # Weights ≈ relative travel cost / distance
    # =================================================

    edges = [

        # Hadapsar ↔ Gadital
        (
            "Hadapsar_Main",
            "Gadital_Chowk",
            4
        ),

        # Hadapsar ↔ Fatima Nagar
        (
            "Hadapsar_Main",
            "FatimaNagar_Junction",
            5
        ),

        # Hadapsar ↔ Magarpatta
        (
            "Hadapsar_Main",
            "Magarpatta_Junction",
            3
        ),

        # Magarpatta ↔ Amanora
        (
            "Magarpatta_Junction",
            "Amanora_Entry",
            2
        ),

        # Gadital ↔ Amanora
        (
            "Gadital_Chowk",
            "Amanora_Entry",
            6
        ),

        # Fatima Nagar ↔ Magarpatta
        (
            "FatimaNagar_Junction",
            "Magarpatta_Junction",
            5
        ),

        # Gadital ↔ Magarpatta
        (
            "Gadital_Chowk",
            "Magarpatta_Junction",
            4
        ),

        # Fatima Nagar ↔ Gadital
        (
            "FatimaNagar_Junction",
            "Gadital_Chowk",
            7
        )
    ]

    # =================================================
    # ADD EDGES
    # =================================================

    for source, destination, weight in edges:

        G.add_edge(

            source,
            destination,

            weight=weight
        )

    return G

# =====================================================
# DIJKSTRA SHORTEST PATH
# =====================================================

def shortest_path(
    G,
    source,
    destination
):

    try:

        path = nx.shortest_path(

            G,

            source=source,

            target=destination,

            weight='weight'
        )

        return path

    except nx.NetworkXNoPath:

        return None

    except Exception as error:

        print("\n===== GRAPH ERROR =====")
        print(error)
        print("=======================\n")

        return None

# =====================================================
# OPTIONAL: PATH COST
# =====================================================

def path_cost(
    G,
    path
):

    try:

        total = 0

        for i in range(len(path) - 1):

            total += G[

                path[i]

            ][

                path[i + 1]

            ]['weight']

        return total

    except Exception:

        return 0

# =====================================================
# OPTIONAL: GRAPH DEBUG
# =====================================================

if __name__ == "__main__":

    graph = create_graph()

    print("\n===== GRAPH NODES =====")

    for node in graph.nodes(data=True):

        print(node)

    print("\n===== GRAPH EDGES =====")

    for edge in graph.edges(data=True):

        print(edge)

    print("\n===== SHORTEST PATH =====")

    result = shortest_path(

        graph,

        "Magarpatta_Junction",

        "Gadital_Chowk"
    )

    print(result)