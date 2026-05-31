import { Hero } from "./Hero.jsx";
import { Features } from "./Features.jsx";
import { CTAs } from "./CTAs.jsx";

export default function Landing() {
  return (
    <>
      <Hero />
      <Features />
      <CTAs />
      <footer style={{ background: "#0a2540", color: "#fff", textAlign: "center", padding: 20, fontSize: 12 }}>
        © {new Date().getFullYear()} Audit Consulting Group · Powered by Audit-IA
      </footer>
    </>
  );
}
