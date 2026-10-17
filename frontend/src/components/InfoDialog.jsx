import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

export default function InfoDialog({ title, children, onClose }) {
	const dialog = useRef(null), titleId = useId();
	useEffect(() => {
		const node = dialog.current, previous = document.activeElement;
		if (typeof node.showModal === "function") node.showModal();
		else node.setAttribute("open", "");
		return () => { node.close?.(); if (previous?.isConnected) previous.focus(); };
	}, []);
	return createPortal(<dialog ref={dialog} className="terminal-dialog" aria-labelledby={titleId} onCancel={onClose} onClose={onClose}><div className="dialog-eyebrow">IOU / FRIENDSHIP FINANCE</div><div className="dialog-head"><h2 id={titleId}>{title}</h2><button className="close" aria-label="Close dialog" onClick={onClose}>×</button></div>{children}</dialog>, document.body);
}
