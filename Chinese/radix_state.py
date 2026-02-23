# radix_state.py
# Consolidated state management, configuration, and validation

import streamlit as st
import json
import uuid
from typing import Any, Dict, List, Optional, Callable
from radix_core import normalize_single_hanzi, resolve_to_known_variant
import streamlit.components.v1 as components


# ==================== CONSTANTS ====================

PAGE_CONFIG = {"layout": "wide", "page_title": "Radix", "page_icon": "🈑"}
PROFILE_SCHEMA_VERSION = 1
PROFILE_FILENAME = "radix_user_data.json"

PAGE_SIZE = 120
GRID_COLUMNS = 10
# MAX_FAVOURITES was removed to allow unlimited favourites
MAX_DERIVATIVES_DISPLAY = 120

DISPLAY_MODES = ["Single Character", "2-Characters", "3-Characters", "4-Characters"]
SCRIPT_FILTERS = ["Any", "Simplified", "Traditional"]

DEFAULT_STATE = {
    "startup_file_choice_made": False,
    "onboarding_done": False,
    "selected_comp": "",
    "stroke_range": (3, 8),
    "radical": "none",
    "component_idc": "none",
    "display_mode": "2-Characters",
    "text_input_comp": "",
    "page": 1,
    "text_input_warning": None,
    "show_inputs": True,
    "last_valid_selected_comp": "",
    "preview_comp": None,
    "stroke_view_active": False,
    "stroke_view_char": "",
    "script_filter": "Any",
    "favourites_list": [],
    "fav_cursor": 0,
    "prompt_config": None,
    "prompt_ui": {"default_selected_task_ids": []},
    "prompt_selected_task_ids": [],
    "history": [],
    "definition_search_mode": False,
    "definition_search_query": "",
    "definition_search_results": None,
    "dataset_editor_mode": False,
    "grid_sort_mode": "usage",
    "grid_script_filter": "Any",
    "derivative_page": 0,  # Track derivatives pagination
}

# ==================== INPUT VALIDATION ====================

class InputValidator:
    """Input validation and normalization."""
    
    @staticmethod
    def validate_character_input(raw: str, error_callback: Optional[Callable] = None) -> Optional[str]:
        """Validate single character input."""
        v = normalize_single_hanzi(raw)
        if not v:
            if error_callback:
                error_callback("One character only")
            return None
        
        resolved = resolve_to_known_variant(v)
        if not resolved:
            if error_callback:
                error_callback("Not found")
            return None
        
        return resolved
    
    @staticmethod
    def validate_definition_search(query: str) -> tuple[bool, Optional[str]]:
        """Validate definition search query."""
        query = query.strip()
        if not query or len(query) < 2:
            return False, "Please enter at least 2 characters to search."
        return True, None

# ==================== STATE MANAGER ====================

class StateManager:
    """Centralized session state management."""
    
    def __init__(self):
        self.state = st.session_state
    
    def initialize(self):
        """Initialize all default state values."""
        for key, value in DEFAULT_STATE.items():
            if key not in self.state:
                self.state[key] = value
    
    # --- Getters ---
    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)
    
    def get_selected_component(self) -> str:
        return self.state.get("selected_comp", "")
    
    def get_preview_component(self) -> Optional[str]:
        return self.state.get("preview_comp")
    
    def get_display_mode(self) -> str:
        return self.state.get("display_mode", "2-Characters")
    
    def get_favourites(self) -> List[str]:
        return self.state.get("favourites_list", [])
    
    def get_history(self) -> List[str]:
        return self.state.get("history", [])
    
    def get_stroke_range(self) -> tuple:
        return self.state.get("stroke_range", (3, 8))
    
    def get_script_filter(self) -> str:
        return self.state.get("script_filter", "Any")
    
    def get_grid_sort_mode(self) -> str:
        return self.state.get("grid_sort_mode", "usage")
    
    def get_current_page(self) -> int:
        return self.state.get("page", 1)
    
    # --- Setters ---
    def set(self, key: str, value: Any):
        self.state[key] = value
    
    def update(self, *args, **kwargs):
        self.state.update(*args, **kwargs)
    
    def pop(self, key: str, default: Any = None) -> Any:
        return self.state.pop(key, default)
    
    # --- Boolean Checks ---
    def is_startup_complete(self) -> bool:
        return self.state.get("startup_file_choice_made", False)
    
    def is_onboarding_complete(self) -> bool:
        return self.state.get("onboarding_done", False)
    
    def is_showing_inputs(self) -> bool:
        return self.state.get("show_inputs", True)
    
    def is_stroke_view_active(self) -> bool:
        return self.state.get("stroke_view_active", False)
    
    def is_definition_search_active(self) -> bool:
        return self.state.get("definition_search_mode", False)

    # --- Navigation Actions ---
    def enter_character_view(self, char: str):
        """Enter character view with given character."""
        # Update URL for persistence
        if char:
            st.query_params["c"] = char

        self.update(
            script_filter="Any",
            selected_comp=char,
            last_valid_selected_comp=char,
            text_input_comp=char,
            text_input_warning=None,
            show_inputs=False,
            preview_comp=None,
            stroke_view_active=False,
            stroke_view_char="",
            display_mode="2-Characters",
            definition_search_mode=False,
            definition_search_results=None,
            derivative_page=0
        )
    
    def go_back(self):
        """Navigate back in history."""
        self.update(
            preview_comp=None,
            stroke_view_active=False,
            stroke_view_char="",
            definition_search_mode=False,
            definition_search_results=None,
            text_input_warning=None
        )
        
        history = self.get_history()
        if history:
            prev = history.pop()
            # Update URL to previous character
            st.query_params["c"] = prev
            
            self.update(
                history=history,
                selected_comp=prev,
                last_valid_selected_comp=prev,
                script_filter="Any",
                show_inputs=False,
                derivative_page=0
            )
        else:
            self.set("show_inputs", True)
            # Clear URL when going back to input list
            if "c" in st.query_params:
                del st.query_params["c"]
    
    def go_to_root(self):
        """Navigate to root/grid view."""
        # Clear URL for persistence
        if "c" in st.query_params:
            del st.query_params["c"]

        self.update(
            history=[],
            preview_comp=None,
            stroke_view_active=False,
            stroke_view_char="",
            text_input_comp="",
            text_input_warning=None,
            selected_comp="",
            show_inputs=True,
            script_filter="Any",
            display_mode="2-Characters",
            definition_search_mode=False,
            definition_search_results=None
        )
    
    def enter_stroke_view(self, char: str):
        """Enter stroke view for character."""
        self.update(
            stroke_view_char=char,
            stroke_view_active=True,
            show_inputs=False
        )
        if not self.get_selected_component():
            self.state["selected_comp"] = char
            self.state["last_valid_selected_comp"] = char
            # Ensure URL is set if we entered stroke view directly
            st.query_params["c"] = char
    
    def exit_stroke_view(self):
        """Exit stroke view."""
        self.update(stroke_view_active=False, stroke_view_char="")
    
    def complete_onboarding(self):
        self.set("onboarding_done", True)
    
    def complete_startup(self):
        self.set("startup_file_choice_made", True)
    
    # --- List Operations ---
    def add_to_favourites(self, char: str):
        """Add character to favourites list (Unlimited)."""
        favs = self.get_favourites()
        if char not in favs:
            # Simply append; no limit check or cursor replacement
            favs.append(char)
            self.set("favourites_list", favs)
    
    def remove_from_favourites(self, char: str):
        favs = self.get_favourites()
        if char in favs:
            favs.remove(char)
            self.set("favourites_list", favs)
    
    def clear_derived_widget_state(self):
        """Clear all derived UI widget states."""
        keys_to_clear = [k for k in list(self.state.keys()) if (
            k == "fav_bulk_editor" or k.startswith("pt_title_") or 
            k.startswith("pt_tpl_") or k.startswith("prompt_task_cb_") or 
            k == "prompt_selected_task_ids" or k == "prompt_default_sel_editor" or 
            k.startswith("fav_chk_")
        )]
        for k in keys_to_clear:
            self.state.pop(k, None)

    def process_search_and_clear(self, raw_input: str, widget_key: str, error_callback=None):
        """Processes search, clears widget, and handles onboarding completion."""
        # Use local import to avoid circular dependency at module level
        from radix_state import InputValidator 
        validated = InputValidator.validate_character_input(raw_input, error_callback)
        if validated:
            self.state[widget_key] = "" # Clear the sticky widget
            self.set("onboarding_done", True) # Ensure we move past splash
            self.enter_character_view(validated)
            return True
        return False

# ==================== CONFIG MANAGER ====================

class ConfigManager:
    """Configuration and profile management."""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
    
    def build_profile_dict(self) -> Dict:
        """Build complete profile dictionary."""
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "favourites_list": self.state.get_favourites(),
            "prompt_config": self.state.get("prompt_config", {}),
            "prompt_ui": self.state.get("prompt_ui", {}),
        }
    
    def export_profile_str(self) -> str:
        """Export profile as JSON string."""
        return json.dumps(self.build_profile_dict(), ensure_ascii=False, indent=2)
    
    def import_profile_dict(self, data: Dict):
        """Import profile from dictionary."""
        if not isinstance(data, dict):
            raise ValueError("Uploaded JSON must be an object.")
        if data.get("schema_version") != PROFILE_SCHEMA_VERSION:
            raise ValueError("Unsupported schema_version.")
        
        self.state.set("favourites_list", data.get("favourites_list", []))
        self.state.set("fav_cursor", 0)
        self.state.set("prompt_config", data.get("prompt_config", {}))
        
        prompt_ui = data.get("prompt_ui", {})
        self.state.set("prompt_ui", prompt_ui if isinstance(prompt_ui, dict) else {})
    
    def import_profile_bytes(self, file_bytes: bytes):
        """Import profile from file bytes."""
        try:
            obj = json.loads(file_bytes.decode("utf-8"))
            self.state.clear_derived_widget_state()
            self.import_profile_dict(obj)
            
            self.state.update({
                "_upload_applied": True,
                "_manual_config_active": True,
                "_post_apply_rerun": True
            })
            
            self.state.pop("_upload_error", None)
            self.normalize_prompt_state()
        except Exception as e:
            self.state.set("_upload_error", f"Invalid JSON: {e}")
            self.state.set("_upload_applied", False)
    
    def load_server_data(self):
        """Load server-side user data if available."""
        if self.state.get("server_data_loaded"):
            return
        
        self.state.set("server_data_loaded", True)
        self.state.set("server_data_available", False)
        
        if self.state.get("_manual_config_active"):
            return
        
        try:
            with open(PROFILE_FILENAME, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict) and obj.get("schema_version") == PROFILE_SCHEMA_VERSION:
                self.state.set("server_data", obj)
                self.state.set("server_data_available", True)
        except FileNotFoundError:
            pass
        except Exception as e:
            st.error(f"Error loading server {PROFILE_FILENAME}: {e}")
    
    def get_default_prompt_config(self) -> Dict:
        """Get default prompt configuration."""
        return {
            "version": 1,
            "preamble": "You are a bilingual Chinese dictionary editor and teacher.\n\nExplain a single Chinese character in depth for language learners. Focus on modern usage, and if the character is rare, show its more widely used modern equivalent while noting the original character.\n\n⸻\n\n",
            "tasks": [
                {"id": "task1", "title": "Task 1 – Character Analysis", "template": "Task 1 – Character Analysis\n\nFor the Hanzi below, provide:\n\t1.\tOriginal meaning – Decompose character into nameable components. Briefly note the ancient form or origin only if it helps understand modern usage.\n\t2.\tCore semantic concept – summarize the main idea in modern context.\n\t3.\tWhy it is used in compound characters – explain how it contributes meaning to words in everyday or contemporary Chinese.\n\t4.\tThree example words – include pinyin and natural English meanings, using modern common usage.\n\t5.\tOne modern usage sentence – show the character in real-life context; if the character is rare, use the modern equivalent and note it.\n\n⸻\n\n"},
                {"id": "task2", "title": "Task 2 – Example Sentences and Images", "template": "Task 2 – Example Sentences and Images\n\nProvide two example sentences that best illustrate modern, everyday usage of the character (or its modern equivalent if the original is rare). For each sentence, include:\na) Traditional Chinese\nb) Simplified Chinese\nc) Natural English translation\nd) Target word/phrase (must include the character or its modern equivalent)\ne) Read-aloud pinyin of the full sentence (with tone marks and natural word grouping)\n\nImages:\n\t•\tIf the character represents a concrete object, generate a realistic image showing its material, context, and typical use.\n\t•\tIf the character represents an abstract concept, quality, or person, do not generate an image.\n\nNote: Only generate images in Task 2 to avoid overlap with analysis or conceptual comparisons.\n\n⸻\n\n"},
                {"id": "task3", "title": "Task 3 – Conceptual Contrast", "template": "Task 3 – Conceptual Contrast\n\nCompare this character with 2–3 other characters of similar meaning or usage, including pinyin. Explain:\n\t•\tHow Chinese divides this concept into different semantic or conceptual systems in modern language usage.\n\t•\tHow the characters differ in real-life usage, highlighting subtle distinctions learners should know.\n\t•\tDo not repeat example sentences from Task 2; only discuss relationships and usage distinctions.\n\n⸻\n\n"},
            ],
            "epilogue": "Hanzi: {char}\n- English definition: {def_en}\n",
        }
    
    def normalize_prompt_state(self):
        """Ensure prompt config and UI state are internally consistent."""
        cfg = self.state.get("prompt_config") or {}
        tasks = cfg.get("tasks", []) or []
        
        # Clean tasks
        cleaned_tasks = []
        seen_ids = set()
        for t in tasks:
            if isinstance(t, dict) and t.get("id") and t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                cleaned_tasks.append(t)
        
        cfg["tasks"] = cleaned_tasks
        self.state.set("prompt_config", cfg)
        
        # Update UI state
        all_task_ids = [t["id"] for t in cleaned_tasks]
        pui = self.state.get("prompt_ui") or {}
        default_ids = pui.get("default_selected_task_ids", [])
        pui["default_selected_task_ids"] = [t for t in default_ids if t in all_task_ids] or list(all_task_ids)
        self.state.set("prompt_ui", pui)
        
        cur_sel = self.state.get("prompt_selected_task_ids") or []
        self.state.set("prompt_selected_task_ids", [t for t in cur_sel if t in all_task_ids] or list(pui["default_selected_task_ids"]))
        
        for tid in all_task_ids:
            key = f"prompt_task_cb_{tid}"
            if key not in self.state.state:
                self.state.state[key] = (tid in self.state.get("prompt_selected_task_ids"))
    
    def initialize_prompt_config(self):
        """Initialize prompt configuration on startup."""
        cfg = self.state.get("prompt_config")
        if cfg is None:
            cfg = self.get_default_prompt_config()
        self.state.set("prompt_config", cfg)
        
        task_ids = [t.get('id') for t in cfg.get('tasks', []) if t.get('id')]
        if not self.state.get("prompt_ui").get('default_selected_task_ids'):
            pui = self.state.get("prompt_ui")
            pui['default_selected_task_ids'] = task_ids
            self.state.set("prompt_ui", pui)
        
        if not self.state.get("prompt_selected_task_ids"):
            self.state.set("prompt_selected_task_ids", list(self.state.get("prompt_ui").get('default_selected_task_ids', task_ids)))
