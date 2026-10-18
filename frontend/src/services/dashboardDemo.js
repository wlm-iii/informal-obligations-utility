export const demoFriends = [
 {id:"maya",display_name:"Maya Chen",email:"maya@example.com",notes:"Boba enthusiast. Always up for a study session."},
 {id:"alex",display_name:"Alex Rivera",email:"alex@example.com",notes:"Concert buddy and keeper of the group playlist."},
 {id:"sam",display_name:"Sam Park",email:"sam@example.com",notes:"Emergency snack supplier."},
 {id:"jules",display_name:"Jules Nguyen",email:"jules@example.com",notes:"Coffee, books, and very good recommendations."},
];
export const demoLoans = [
 {id:"1",friend_id:"maya",kind:"money",description:"Boba acquisition / extra pearls, extra debt",outstanding_cents:1850,principal_cents:1850,repaid_cents:0,status:"open",overdue:true,due_date:"2026-10-15",lent_at:"2026-10-01"},
 {id:"2",friend_id:"alex",kind:"money",description:"Concert financing / emotionally necessary",outstanding_cents:6000,principal_cents:8500,repaid_cents:2500,status:"open",overdue:false,due_date:"2026-10-24",lent_at:"2026-10-03"},
 {id:"3",friend_id:"sam",kind:"item",description:"Blue hoodie",status:"open",overdue:false,due_date:"2026-10-20",lent_at:"2026-10-05"},
 {id:"4",friend_id:"jules",kind:"item",description:"The Little Prince",status:"completed",overdue:false,due_date:"2026-10-18",lent_at:"2026-10-02",returned_at:"2026-10-12"},
];

export const demoPayments = [
 {action:"repayment",amount_cents:500,effective_at:"2026-10-04T12:00:00Z"},
 {action:"repayment",amount_cents:750,effective_at:"2026-10-08T12:00:00Z"},
 {action:"repayment",amount_cents:1250,effective_at:"2026-10-14T12:00:00Z"},
];

export const referenceLoans = demoLoans.map(l => l.id === "1" ? {...l,kind:"item",description:"Travel mug",principal_cents:null,outstanding_cents:null,repaid_cents:null} : l.id === "2" ? {...l,description:"Concert tickets",interest_percent:2,repayment_type:"money",due_date:"2026-10-15",overdue:true,principal_cents:38500,outstanding_cents:12500,repaid_cents:26000} : l);
export const referencePayments = [["2026-07-01",2500,"Lunch & coffee"],["2026-07-26",3000,"Concert tickets"],["2026-08-14",3000,"Lunch & coffee"],["2026-08-29",5000,"Concert tickets"],["2026-09-13",3000,"Lunch & coffee"],["2026-09-28",4000,"Concert tickets"],["2026-10-06",2500,"Concert tickets"],["2026-10-14",3000,"Concert tickets"]].map(([date,amount,description],i)=>({id:`preview-payment-${i}`,loan_id:"2",action:"repayment",effective_at:`${date}T12:00:00Z`,amount_cents:amount,description}));
