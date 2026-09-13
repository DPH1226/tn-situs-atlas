# How the queue works — in plain English

*For a finance director who has never thought about situs codes and should not have to.*

## The one fact everything rests on

When a business registers for sales tax in Tennessee, someone types an address into a form. The
Department of Revenue turns that address into a four-digit code — the first two digits for the county,
the last two for the city, "00" meaning outside any city. That code decides where the local sales tax
goes, every month, for as long as the business exists. **Nobody at the State ever goes back and checks
it against a map.** If the address on the form was the mailing address instead of the physical one,
or the clerk picked the wrong city, or the city limits moved after the form was filed, the money goes
to the wrong government indefinitely — until the government losing it notices and says so.

The State keeps a map of where each code applies. The State also keeps a list of every business and
its code. **The State does not compare the two.** That comparison is the entire job.

## What we can see without the State's list

The map is public. So is every address in the county (from the 911 district — the people who make sure
an ambulance finds your house), every city limit (from the Comptroller), and a second State file that
says which code goes with each street and house-number range.

So before we ever see the State's list, we already know two things about every business address in the
county: **which code it *should* have**, and **how likely it is that the form was filled out wrong.**
The second part is what the queue ranks.

## What puts a business in the queue, and why

**1. "Cross-county postal" — the mailing address says a different county.**
Old Hickory is a Davidson County post office, but its delivery area runs across the county line into
Wilson. A business on Lebanon Road in Mt. Juliet gets its mail addressed "Old Hickory, TN 37138." If
that business wrote its mailing address on the sales-tax form — which is what most people write — the
State coded it to Davidson County. Wilson County loses the school half *and* the situs half, and no
one notices, because the tax rate is the same on both sides of the line and the customer never sees a
difference. These are the most expensive errors, so they go first. In Wilson there are 74 named
businesses in this situation.

**2. "Coded ≠ measured" — the State's list says one code, the map says another.**
This one only exists after the situs report arrives. It is the actual finding. Everything else in the
queue exists to make sure these get found fast.

**3. "Boundary risk" — the building is within 250 feet of a line.**
Not an error. A caution. When a business sits 40 feet from the Lebanon city limit, any map or any
address database can put it on the wrong side, including ours. So these are never processed
automatically: within 250 feet a person checks every source, and within 50 feet a person has to sign
off before anything is submitted. This is the rule that keeps us out of an argument we would lose.

**4. "Postal exposure" — the mailing address names a city the building isn't in.**
Huge parts of unincorporated Wilson County have Lebanon or Mt. Juliet mailing addresses. A business
there that wrote its mailing address on the form got coded to the city, and the situs half went to the
city instead of the county. This is the biggest group — 431 named businesses in Wilson — but the
cheapest kind of error, because only half the tax is at stake and it stays inside the county.

**Everything else** is a business whose mailing city, physical location and every official source all
agree. They are listed, so nothing is hidden, but they sort last.

## What the ranking is worth

Hendersonville publishes its business roster *with* the State's codes on it, which let us test the
ranking against reality. Of 1,945 businesses we could place on the map, six were coded wrong. The
"postal exposure" rule flagged sixteen businesses and five of the six wrong ones were among them.
The sixth was 123 feet from a city limit and the boundary rule caught it. **So reading 64 rows out of
1,945 finds all six errors.** That is the difference between an audit that takes a day and one that
takes a month, and it is what the queue is for.

## What is *not* in the queue, on purpose

The county's 911 district labels things on its map that are not businesses — subdivisions, lot
numbers, pump stations, churches, schools. Those are shown on the map so nothing is hidden, but they
never appear as an audit item. An audit the county has to stand behind cannot contain a row called
"Lot 19."

## One thing we can prove today, without the State's list

The State publishes the map, and it publishes the street-by-street code file. They should agree.
On 12,691 Wilson County addresses they don't — and not by a few feet; every one of these is more than
250 feet from any boundary. Gaston Park Drive in Lebanon is a good example: the street file says the
whole street is unincorporated county; the map, the Comptroller and the 911 district all say it is
inside Lebanon. The street file is what online sellers and marketplaces use to decide where your local
tax goes when they ship to that address. Every online sale to Gaston Park Drive is being allocated to
the county instead of the city. In Wilson the direction runs about three-to-one in the county's
favour. That is a finding about the State's own data, and it can be shown to the Department now.
