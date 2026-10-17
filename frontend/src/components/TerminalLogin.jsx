import { useEffect, useRef } from "react";
import { supabase } from "../services/supabase";
import { loginRequest } from "../services/login";

export default function TerminalLogin() {
	const frame = useRef(null);
	useEffect(() => {
		let busy = false, active = true;
		async function receive(event) {
			if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow || event.data?.type !== "iou:login") return;
			if (busy) return;
			busy = true;
			let error = "";
			try { await loginRequest(supabase?.auth, event.data, window.location.origin); }
			catch (failure) { error = failure.message; }
			finally {
				busy = false;
				if (active) event.source.postMessage({ type: "iou:login-result", error }, window.location.origin);
			}
		}
		window.addEventListener("message", receive);
		return () => { active = false; window.removeEventListener("message", receive); };
	}, []);
	return <iframe ref={frame} title="IOU sign in" src="/IOU-Terminal-Login.html?connected=1" style={{ position: "fixed", inset: 0, width: "100%", height: "100%", border: 0, zIndex: 1 }} />;
}
