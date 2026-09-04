import { EnvironmentBanner } from "../src/components/environment-banner";
import { PilotWorkspace } from "../src/components/pilot-workspace";

export default function HomePage() {
  return (
    <main>
      <EnvironmentBanner />
      <PilotWorkspace />
    </main>
  );
}
