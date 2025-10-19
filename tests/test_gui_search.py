import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rs


class DummyStringVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class FakeTree:
    def __init__(self) -> None:
        self.nodes = {"": []}
        self.parents = {}
        self.items = {}
        self._selection: list[str] = []
        self._focus = ""

    def selection(self):
        return tuple(self._selection)

    def selection_set(self, nodes):
        self._selection = list(nodes)

    def selection_remove(self, nodes):
        removal = set(nodes)
        self._selection = [node for node in self._selection if node not in removal]

    def focus(self, node=None):
        if node is None:
            return self._focus
        self._focus = node
        return node

    def see(self, node):
        return node

    def get_children(self, node=""):
        return tuple(self.nodes.get(node, []))

    def delete(self, *nodes):
        for node in nodes:
            self._delete_node(node)

    def _delete_node(self, node: str) -> None:
        for child in list(self.nodes.get(node, [])):
            self._delete_node(child)
        parent = self.parents.pop(node, "")
        if parent in self.nodes:
            self.nodes[parent] = [child for child in self.nodes[parent] if child != node]
        self.nodes.pop(node, None)
        self.items.pop(node, None)
        self._selection = [item for item in self._selection if item != node]
        if self._focus == node:
            self._focus = ""

    def insert(self, parent, index, text="", values=(), open=False, tags=()):
        parent = parent or ""
        node_id = f"iid{len(self.items) + 1}"
        self.parents[node_id] = parent
        self.nodes.setdefault(parent, []).append(node_id)
        self.nodes.setdefault(node_id, [])
        self.items[node_id] = {
            "text": text,
            "values": values,
            "open": bool(open),
            "tags": tags,
        }
        return node_id

    def item(self, node, option=None, **kwargs):
        if kwargs:
            if node in self.items:
                self.items[node].update(kwargs)
            return
        if option == "open":
            return self.items.get(node, {}).get("open", False)
        if option:
            return self.items.get(node, {}).get(option)
        return dict(self.items.get(node, {}))

    def exists(self, node):
        return node in self.items

    def identify_row(self, _y):
        if self._selection:
            return self._selection[-1]
        if self._focus and self._focus in self.items:
            return self._focus
        return ""


class TextureManagerGUISearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_tk = rs.tk
        rs.tk = types.SimpleNamespace(TclError=Exception)

        self.gui = object.__new__(rs.TextureManagerGUI)
        self.gui.tree = FakeTree()
        self.gui.search_var = DummyStringVar()
        self.gui.image_entries = [
            {"relative_path": "textures/alpha.dds", "size": 10, "offset": 0},
            {"relative_path": "textures/beta.dds", "size": 12, "offset": 10},
            {"relative_path": "icons/gamma.png", "size": 8, "offset": 22},
        ]
        self.gui.entries = list(self.gui.image_entries)
        self.gui.replacements = {}
        self.gui.node_to_entry = {}
        self.gui.entry_nodes = {}
        self.gui.node_to_path = {}
        self.gui.last_activated_path = None
        self.gui._expand_all_on_refresh = False
        self.gui._set_status = lambda _message: None
        self.gui._set_channel_controls_state = lambda _state: None
        self.gui.cleared_messages: list[str | None] = []

        def clear_preview(instance, message=None):
            instance.cleared_messages.append(message)
            instance.last_activated_path = None
            instance.selected_preview = None

        def on_entry_selected(instance, _event):
            selection = [
                node
                for node in instance.tree.selection()
                if node in instance.node_to_entry
            ]
            instance.selected_preview = (
                instance.node_to_entry[selection[-1]]["relative_path"]
                if selection
                else None
            )

        self.gui._clear_preview = types.MethodType(clear_preview, self.gui)
        self.gui._on_entry_selected = types.MethodType(on_entry_selected, self.gui)
        self.gui.selected_preview = None

        self.gui._refresh_list()

    def tearDown(self) -> None:
        rs.tk = self.original_tk

    def test_search_filters_entries_and_updates_tree(self) -> None:
        initial_paths = set(self.gui.entry_nodes.keys())
        self.assertIn("textures/alpha.dds", initial_paths)
        self.assertIn("textures/beta.dds", initial_paths)
        self.assertIn("icons/gamma.png", initial_paths)

        alpha_node = self.gui.entry_nodes["textures/alpha.dds"]
        self.gui.tree.selection_set([alpha_node])
        self.gui.tree.focus(alpha_node)
        self.gui.last_activated_path = "textures/alpha.dds"

        self.gui.search_var.set("beta")
        self.gui._apply_search_filter()

        filtered_paths = [entry["relative_path"] for entry in self.gui.entries]
        self.assertEqual(filtered_paths, ["textures/beta.dds"])
        self.assertEqual(set(self.gui.entry_nodes.keys()), {"textures/beta.dds"})
        self.assertEqual(self.gui.cleared_messages[-1], None)

        beta_node = self.gui.entry_nodes["textures/beta.dds"]
        self.gui.tree.selection_set([beta_node])
        self.gui.tree.focus(beta_node)
        self.gui.last_activated_path = "textures/beta.dds"

        self.gui.search_var.set("")
        self.gui._apply_search_filter()

        self.assertEqual(
            {entry["relative_path"] for entry in self.gui.entries},
            {"textures/alpha.dds", "textures/beta.dds", "icons/gamma.png"},
        )
        self.assertEqual(set(self.gui.entry_nodes.keys()), initial_paths)

        self.gui.search_var.set("gamma")
        self.gui._apply_search_filter()

        self.assertIsNone(self.gui.selected_preview)
        self.assertEqual(
            [entry["relative_path"] for entry in self.gui.entries],
            ["icons/gamma.png"],
        )
        self.assertEqual(self.gui.cleared_messages[-1], None)


if __name__ == "__main__":
    unittest.main()
