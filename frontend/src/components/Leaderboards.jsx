import "./Leaderboards.css";
import { rankEntries } from "../services/leaderboards";

const boards = [
  {
    "label": "Hall of Fame awards",
    "entries": [
      {
        "name": "Alex",
        "score": 740,
        "title": "Walking ATM",
        "art": "fame-art atm"
      },
      {
        "name": "Jordan",
        "score": 825,
        "title": "Credit Royalty",
        "art": "fame-art royalty"
      },
      {
        "name": "Sam",
        "score": 710,
        "title": "Speedrun Champion",
        "art": "fame-art speedrun"
      },
      {
        "name": "Taylor",
        "score": 790,
        "title": "Certified Green Flag",
        "art": "fame-art greenflag"
      }
    ]
  },
  {
    "label": "Hall of Shame awards",
    "entries": [
      {
        "name": "Alex",
        "score": 420,
        "title": "Public Enemy #1",
        "art": "wanted"
      },
      {
        "name": "Jordan",
        "score": 510,
        "title": "Debt Criminal",
        "art": "criminal"
      },
      {
        "name": "Sam",
        "score": 580,
        "title": "Brokie Alert",
        "art": "brokie"
      },
      {
        "name": "Riley",
        "score": 390,
        "title": "Professional Ghoster",
        "art": "ghoster"
      }
    ]
  }
];


export default function Leaderboards() {
 return <section className="leaderboards" aria-labelledby="leaderboards-heading">
  <header><p className="eyebrow">GOOD FRIENDS. GREAT TRACK RECORDS.</p><h1 id="leaderboards-heading">THE LEADERBOARDS.</h1></header>
  <div className="hall-columns">{boards.map((board, index) => <section className={`hall ${index ? "shame" : "fame"}`} key={board.label} aria-label={index ? "Hall of Shame" : "Hall of Fame"}>
   <h2>{index ? "Hall of Shame" : "Hall of Fame"}</h2>
   <ol>{rankEntries(board.entries, Boolean(index)).map(entry => <li key={entry.title}>
    <span className={`hall-art ${index ? "shame-art" : "fame-art"} ${entry.art}`} role="img" aria-label={`${entry.title} illustration`} />
    <span className="hall-name">{entry.name}</span><h3>{entry.title}</h3>
    <span className="hall-credit">Fictional score <strong>{entry.score}</strong></span>
   </li>)}</ol>
  </section>)}</div>
  <p className="hall-disclaimer">Illustrative sample names and scores. Awards and qualification rules are a design preview; no private ledger data is connected. Fictional IOU score — for fun, not a real credit score.</p>
 </section>;
}
