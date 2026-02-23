# radix_persistence.py
# URL-based persistence with localStorage backup (Characters + Favourites)

import streamlit as st
from streamlit.components.v1 import html as st_html

class SessionPersistence:
    """Clean URL-based persistence"""
    
    @staticmethod
    def get_auto_save_script(char: str, favs: list) -> str:
        """Save character and favourites to localStorage as backup"""
        safe_char = char or ""
        safe_favs = ",".join(favs) if favs else ""
        return f"""<script>
try {{ 
    localStorage.setItem('radix_last', '{safe_char}'); 
    localStorage.setItem('radix_favs', '{safe_favs}');
}}
catch(e) {{ console.log('Save skipped'); }}
</script>"""
    
    @staticmethod
    def get_resume_button(base_url: str) -> str:
        """Smart resume button that reads localStorage for Char + Favs"""
        return f"""
<div id="resume-container" style="text-align:center; margin:25px 0; display:none;">
    <a id="resume-link" href="#" style="
        display: inline-flex; align-items: center; gap: 10px;
        padding: 14px 28px; border-radius: 12px;
        background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
        color: white; text-decoration: none; font-weight: 700;
        font-size: 16px; box-shadow: 0 4px 12px rgba(76,175,80,0.3);
        transition: all 0.2s ease; border: 2px solid #2e7d32;
    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 16px rgba(76,175,80,0.4)';"
       onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(76,175,80,0.3)';">
        <span style="font-size:24px;">🔄</span>
        <span id="resume-text">Resume Session</span>
    </a>
    <div style="font-size:13px; color:#666; margin-top:8px;">Restores character & favourites</div>
</div>
<script>
(()=>{{
    try {{
        const savedChar = localStorage.getItem('radix_last');
        const savedFavs = localStorage.getItem('radix_favs');
        
        if (!savedChar || savedChar.length !== 1) return;
        
        const link = document.getElementById('resume-link');
        const text = document.getElementById('resume-text');
        const container = document.getElementById('resume-container');
        
        // Build URL with char AND favourites
        let url = '{base_url}'.replace(/\/$/, '') + '/?c=' + encodeURIComponent(savedChar);
        if (savedFavs && savedFavs.length > 0) {{
            url += '&favs=' + encodeURIComponent(savedFavs);
        }}
        
        link.href = url;
        text.textContent = 'Resume: ' + savedChar;
        container.style.display = 'block';
        
        // Handle click
        link.onclick = (e) => {{
            e.preventDefault();
            text.textContent = 'Restoring...';
            try {{ window.top.location.href = url; }}
            catch(err) {{ window.open(url, '_blank'); }}
        }};
    }} catch(e) {{ console.log('Resume unavailable'); }}
}})();
</script>"""
    
    @staticmethod
    def get_heartbeat() -> str:
        """Lightweight heartbeat"""
        return """<script>
setInterval(()=>fetch(window.location.href,{headers:{'Cache-Control':'no-cache'}}).catch(()=>{}),45000);
</script>"""


class PersistenceManager:
    """Minimal persistence manager"""
    
    def __init__(self, state_manager):
        self.state = state_manager
        default_base_url = "https://chinese-5n7qfcqoljkixr2spprdbr.streamlit.app"
        try:
            app_cfg = st.secrets.get("app", {})
            if isinstance(app_cfg, dict):
                self.base_url = app_cfg.get("base_url", default_base_url)
            else:
                self.base_url = default_base_url
        except Exception:
            # Local/dev or read-only deployments may not provide secrets.toml.
            self.base_url = default_base_url
    
    def auto_save(self):
        """Save current character AND favourites to localStorage"""
        char = self.state.get_selected_component()
        favs = self.state.get_favourites()
        
        # Save if we have a character OR favourites (don't lose favs if just browsing grid)
        if (char or favs):
            st_html(SessionPersistence.get_auto_save_script(char, favs), height=0)
    
    def try_restore(self):
        """Check URL param ?c= and ?favs= and restore if present"""
        
        # 1. Restore Favourites (do this first so they exist regardless of character)
        favs_param = st.query_params.get("favs")
        if favs_param:
            from radix_state import InputValidator
            raw_list = favs_param.split(",")
            valid_favs = []
            for f in raw_list:
                v = InputValidator.validate_character_input(f)
                if v and v not in valid_favs:
                    valid_favs.append(v)
            if valid_favs:
                self.state.set("favourites_list", valid_favs)

        # 2. Restore Character
        if self.state.get_selected_component():
            return
        
        char_param = st.query_params.get("c")
        if not char_param:
            return
        
        # Validate the character
        from radix_state import InputValidator
        validated = InputValidator.validate_character_input(char_param)
        
        if validated:
            # Deep restore: skip all startup screens
            self.state.state["startup_file_choice_made"] = True
            self.state.state["onboarding_done"] = True
            
            # Navigate to character
            self.state.enter_character_view(validated)
            
            msg = f"📍 Restored: {validated}"
            if favs_param:
                msg += f" + {len(self.state.get_favourites())} Favourites"
            st.toast(msg, icon="✅")
    
    def show_resume_option(self):
        """Show resume button on splash screen"""
        st_html(SessionPersistence.get_resume_button(self.base_url), height=110)
    
    def add_heartbeat(self):
        """Add invisible heartbeat"""
        if self.state.is_onboarding_complete():
            st_html(SessionPersistence.get_heartbeat(), height=0)
    
    def render_controls(self):
        """Minimal status in sidebar"""
        with st.expander("💾 Session Status", expanded=False):
            char = self.state.get_selected_component()
            favs = self.state.get_favourites()
            
            if char:
                st.success(f"📍 Current: **{char}**")
                st.caption("✅ URL bookmark active")
                st.caption("✅ Heartbeat running")
            else:
                st.info("Navigate to a character to enable persistence")
            
            if favs:
                st.caption(f"⭐ {len(favs)} Favourites tracked")
            
            st.markdown("---")
            
            if st.button("🗑️ Clear History", use_container_width=True):
                st_html("<script>localStorage.removeItem('radix_last'); localStorage.removeItem('radix_favs');</script>", height=0)
                st.toast("History cleared")
            
            with st.expander("ℹ️ How It Works"):
                st.caption("""
                **URL Persistence:**
                - Characters update URL (e.g., `?c=水`)
                - Favourites included in resume links
                
                **Backup Storage:**
                - Character & Favourites saved to localStorage
                - Resume button appears on splash screen
                """)
