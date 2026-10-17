import { createRoot } from "react-dom/client";
import Dashboard from "./components/Dashboard";
import { demoFriends, demoLoans } from "./services/dashboardDemo";
import "./index.css";
const demo = { friends: demoFriends, loans: demoLoans };
createRoot(document.getElementById("root")).render(<Dashboard demo={demo} profile={{ display_name: "Anca" }} account={<p>Sample account. Sign in to the main app to view your private profile.</p>}/>);
