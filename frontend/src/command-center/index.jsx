import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import "./styles.css";
import Topbar from "./components/Topbar.jsx";
import LayerSidebar from "./components/LayerSidebar.jsx";
import ActivityPanel from "./components/ActivityPanel.jsx";
import GovernanceBar from "./components/GovernanceBar.jsx";
import Workspace from "./components/Workspace.jsx";
import LayerWorkspace from "./components/LayerWorkspace.jsx";
import GovernancePanel from "./components/GovernancePanel.jsx";

export default function CommandCenter() {
  const [section, setSection] = useState("overview");
  const [navOpen, setNavOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [section]);

  function select(id) {
    setSection(id);
    setNavOpen(false);
  }

  return (
    <div id="ab-os" className="ab-min-h-screen ab-font-sans ab-text-ab-ink">
      <Topbar
        onToggleNav={() => setNavOpen((o) => !o)}
        onToggleActivity={() => setActivityOpen((o) => !o)}
      />
      <div className="ab-flex">
        <LayerSidebar
          section={section}
          onSelect={select}
          open={navOpen}
          onClose={() => setNavOpen(false)}
        />

        <main className="ab-min-w-0 ab-flex-1">
          <div className="ab-h-[calc(100vh-3.5rem-2.25rem)] ab-overflow-y-auto">
            <div className="ab-mx-auto ab-max-w-[1280px] ab-px-4 ab-py-5 sm:ab-px-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={section}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.28 }}
                >
                  {section === "overview" && (
                    <Workspace
                      onOpenLayer={select}
                      onOpenGov={() => select("GOV")}
                    />
                  )}
                  {section === "GOV" && (
                    <GovernancePanel onBack={() => select("overview")} />
                  )}
                  {section !== "overview" && section !== "GOV" && (
                    <LayerWorkspace
                      code={section}
                      onBack={() => select("overview")}
                    />
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
          <GovernanceBar onOpen={() => select("GOV")} />
        </main>

        <ActivityPanel
          open={activityOpen}
          onClose={() => setActivityOpen(false)}
        />
      </div>
    </div>
  );
}
