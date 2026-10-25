import networkx as nx

from recon.schemas import CFG, Block, Edge, Instruction


def build_cfg(instructions: list[Instruction]) -> CFG:
    if not instructions:
        return CFG()
    addresses = {i.address for i in instructions}
    leaders = {instructions[0].address}
    for pos, ins in enumerate(instructions):
        if ins.flow in {"jump", "conditional"} and ins.branch_target in addresses:
            leaders.add(ins.branch_target)
        if ins.flow in {"jump", "conditional", "return", "stop"} and pos + 1 < len(instructions):
            leaders.add(instructions[pos + 1].address)
    chunks: list[list[Instruction]] = []
    for ins in instructions:
        if ins.address in leaders:
            chunks.append([])
        chunks[-1].append(ins)
    blocks = [
        Block(
            id=f"b_{part[0].address:x}",
            start_address=part[0].address,
            end_address=part[-1].address + part[-1].size,
            instruction_addresses=[i.address for i in part],
        )
        for part in chunks
    ]
    lookup = {b.start_address: b.id for b in blocks}
    edges: list[Edge] = []
    unresolved: list[int] = []
    for pos, (block, part) in enumerate(zip(blocks, chunks, strict=True)):
        last = part[-1]
        if last.flow in {"jump", "conditional"}:
            if last.branch_target in lookup:
                edges.append(
                    Edge(source=block.id, target=lookup[last.branch_target], kind="branch")
                )
            else:
                unresolved.append(last.address)
        if (last.flow in {"next", "call", "conditional"} and pos + 1 < len(blocks)
                and last.address + last.size == blocks[pos + 1].start_address):
            edges.append(Edge(source=block.id, target=blocks[pos + 1].id, kind="fallthrough"))
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_nodes_from(b.id for b in blocks)
    graph.add_edges_from((e.source, e.target) for e in edges)
    components = nx.number_weakly_connected_components(graph)
    return CFG(
        blocks=blocks,
        edges=edges,
        unresolved_branches=unresolved,
        statistics={
            "blocks": float(len(blocks)),
            "edges": float(len(edges)),
            "cyclomatic_complexity": float(graph.number_of_edges() - len(blocks) + 2 * components),
            "components": float(components),
            "density": float(nx.density(graph)),
            "branch_ratio": sum(i.flow == "conditional" for i in instructions) / len(instructions),
        },
    )
