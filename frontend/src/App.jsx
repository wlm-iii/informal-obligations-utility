import "./App.css";

import RandomItem from "@/components/RandomItem";

function App() {
	return (
		<main>
			<p className="eyebrow">Informal Obligations Utility</p>
			<h1>IOU</h1>
			<p>Your friends forget. We don’t.</p>
			<p>A private ledger for borrowed money, missing hoodies, and fictional credit scores.</p>
			<section className="card" aria-label="Development status">
				<h2>Under construction</h2>
				<p>This is the project foundation, not a working lending app yet.</p>
				<RandomItem maximum={1000} />
			</section>
		</main>
	);
}

export default App;
