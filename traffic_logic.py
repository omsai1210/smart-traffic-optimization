import random

# =====================================================
# TRAFFIC GENERATION
# =====================================================

def generate_traffic(G):

    """
    Generates simulated traffic density
    for each edge in the graph.

    Higher value = higher congestion
    """

    traffic = {}

    for edge in G.edges():

        # traffic intensity
        traffic[edge] = random.randint(1, 10)

    return traffic

# =====================================================
# GREEDY DYNAMIC SIGNAL SELECTION
# =====================================================

def dynamic_signal(
    node,
    G,
    traffic
):

    """
    Greedy approach:
    Select edge with highest congestion
    around current node.

    This signal gets highest priority.
    """

    connected_edges = []

    for neighbor in G.neighbors(node):

        edge = (node, neighbor)

        reverse_edge = (neighbor, node)

        # graph edge may exist in either order
        if edge in traffic:

            connected_edges.append(edge)

        elif reverse_edge in traffic:

            connected_edges.append(reverse_edge)

    if not connected_edges:

        return None

    # GREEDY:
    # choose most congested nearby edge
    best_edge = max(

        connected_edges,

        key=lambda e: traffic[e]
    )

    return best_edge

# =====================================================
# DYNAMIC GREEN SIGNAL TIME
# =====================================================

def dynamic_time(traffic_value):

    """
    Dynamically allocate
    green signal timing
    based on congestion.

    More congestion = longer green
    """

    # minimum green time
    base_time = 5

    # adaptive extension
    extension = traffic_value * 2

    return base_time + extension

# =====================================================
# DELAY CALCULATION & MODE COMPARISON
# =====================================================

def calculate_segment_delay(congestion, mode="dynamic"):

    """
    Computes realistic intersection delay (in seconds) based on congestion (1-10).
    Higher congestion increases delay in both modes, but adaptive greedy signal
    scheduling significantly mitigates queue buildup compared to rigid fixed-time cycles.
    """

    if mode == "fixed":

        # Fixed timer: static cycles cause compounding delays as queues build up
        return round(15.0 + 4.5 * congestion, 2)

    else:

        # Dynamic greedy: adaptive green time clears queues faster while
        # delay still scales naturally with vehicle volume
        return round(8.0 + 1.8 * congestion, 2)

def compare_modes(
    path,
    traffic
):

    """
    Compare fixed signal system
    vs dynamic greedy system along the given path.
    """

    fixed_total = 0.0
    dynamic_total = 0.0

    for i in range(len(path) - 1):

        edge = (
            path[i],
            path[i + 1]
        )

        reverse_edge = (
            path[i + 1],
            path[i]
        )

        # handle reverse storage
        if edge in traffic:

            congestion = traffic[edge]

        else:

            congestion = traffic.get(
                reverse_edge,
                5
            )

        # ================= DELAY ACCUMULATION =================

        fixed_delay = calculate_segment_delay(
            congestion,
            mode="fixed"
        )

        dynamic_delay = calculate_segment_delay(
            congestion,
            mode="dynamic"
        )

        fixed_total += fixed_delay
        dynamic_total += dynamic_delay

    fixed_total = round(fixed_total, 2)
    dynamic_total = round(dynamic_total, 2)

    # ================= EFFICIENCY =================

    if fixed_total == 0:

        efficiency = 0

    else:

        efficiency = round(

            (
                (fixed_total - dynamic_total)
                / fixed_total
            ) * 100,

            2
        )

    return {

        "fixed": fixed_total,

        "dynamic": dynamic_total,

        "efficiency": efficiency
    }

# =====================================================
# OPTIONAL DEBUG
# =====================================================

if __name__ == "__main__":

    from graph import create_graph

    graph = create_graph()

    traffic_data = generate_traffic(graph)

    print("\n===== TRAFFIC =====")

    for edge, value in traffic_data.items():

        print(edge, "→", value)

    print("\n===== SIGNAL PRIORITY =====")

    for node in graph.nodes():

        best = dynamic_signal(
            node,
            graph,
            traffic_data
        )

        print(node, "→", best)

    print("\n===== COMPARISON =====")

    sample_path = [

        "Magarpatta_Junction",

        "Gadital_Chowk"
    ]

    result = compare_modes(
        sample_path,
        traffic_data
    )

    print(result)