# backend/utils/call_graph_tracer.py
# Solution de tracing de fonctions proposé par Claude3 le 34/04/25

from functools import wraps
import time
import json
import inspect
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class CallNode:
    function_name: str
    start_time: float
    end_time: float = 0
    duration: float = 0
    args: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    children: List['CallNode'] = field(default_factory=list)
    level: int = 0
    
class CallGraphTracer:
    def __init__(self):
        self.root_nodes: List[CallNode] = []
        self.current_stack: List[CallNode] = []
        
    def trace(self, name=None):
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._execute_with_tracing(func, name, *args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self._execute_with_tracing(func, name, *args, **kwargs)
            
            return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        return decorator
        
    async def _execute_with_tracing(self, func, custom_name, *args, **kwargs):
        function_name = custom_name or func.__name__
        call_node = CallNode(
            function_name=function_name,
            start_time=time.time(),
            args=self._extract_args(func, args, kwargs),
            level=len(self.current_stack)
        )
        
        # Ajouter au graphe
        if self.current_stack:
            self.current_stack[-1].children.append(call_node)
        else:
            self.root_nodes.append(call_node)
            
        self.current_stack.append(call_node)
        
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            call_node.result = str(result)[:100] if result else None
            return result
            
        finally:
            call_node.end_time = time.time()
            call_node.duration = call_node.end_time - call_node.start_time
            self.current_stack.pop()
            
    def _extract_args(self, func, args, kwargs):
        # Extraire les noms des arguments
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return {k: str(v)[:50] for k, v in bound.arguments.items()}
    
    def generate_mermaid_diagram(self) -> str:
        """Génère un diagramme Mermaid à partir du graphe d'appels"""
        mermaid_lines = ["graph TD"]
        
        def process_node(node: CallNode, parent_id=None, counter=[0]):
            node_id = f"node{counter[0]}"
            counter[0] += 1
            
            label = f"{node.function_name}\n{node.duration*1000:.1f}ms"
            mermaid_lines.append(f'    {node_id}["{label}"]')
            
            if parent_id:
                mermaid_lines.append(f'    {parent_id} --> {node_id}')
                
            for child in node.children:
                process_node(child, node_id, counter)
                
        for root in self.root_nodes:
            process_node(root)
            
        return "\n".join(mermaid_lines)
    
    def generate_html_report(self) -> str:
        """Génère un rapport HTML interactif"""
        mermaid_diagram = self.generate_mermaid_diagram()
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Nova Call Graph</title>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .mermaid {{ background-color: #f5f5f5; padding: 20px; }}
                .stats {{ margin-top: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Nova Call Graph Analysis</h1>
            <div class="mermaid">
                {mermaid_diagram}
            </div>
            <div class="stats">
                <h2>Function Call Statistics</h2>
                <table>
                    <tr>
                        <th>Function</th>
                        <th>Duration (ms)</th>
                        <th>Calls</th>
                    </tr>
                    {self._generate_stats_table()}
                </table>
            </div>
            <script>
                mermaid.initialize({{ startOnLoad: true }});
            </script>
        </body>
        </html>
        """
    
    def _generate_stats_table(self) -> str:
        stats = {}
        
        def collect_stats(node: CallNode):
            name = node.function_name
            if name not in stats:
                stats[name] = {"duration": 0, "calls": 0}
            stats[name]["duration"] += node.duration * 1000
            stats[name]["calls"] += 1
            
            for child in node.children:
                collect_stats(child)
        
        for root in self.root_nodes:
            collect_stats(root)
            
        rows = []
        for func, data in sorted(stats.items(), key=lambda x: x[1]["duration"], reverse=True):
            rows.append(f"""
                <tr>
                    <td>{func}</td>
                    <td>{data['duration']:.2f}</td>
                    <td>{data['calls']}</td>
                </tr>
            """)
            
        return "\n".join(rows)

# Instance globale
call_tracer = CallGraphTracer()