# Policy

## The New-work test

**A standup is people reporting progress on work that already exists. Almost nothing in one is a new issue.** The
characteristic failure is proposing "finish the spec fixes and share the product for testing" from a standup line about
work already in flight: a status update wearing an issue's clothes, which creates a duplicate of something already
being done.

Before proposing anything, an item must pass **all four**:

1. **Search the tracker first.** Search for the topic every time, with a real search, not a title match. If an issue
   already covers it, do not propose: note the existing key in the state file and move on. This is a required call.
2. **Is it new?** "Finish", "continue", "carry on with", "keep going", "wrap up", "still working on" describe work that
   already exists. A person reporting what they did yesterday or will do today is not creating work. Propose only
   what came into existence *in this meeting*.
3. **Did someone decide it?** A discussion, an idea floated or a "we should maybe" is not a decision. If the meeting
   did not settle that this will be done, it is not an issue.
4. **Would it survive a week?** If nobody would care about this ticket in seven days, it is a note, not an issue.

When in doubt, do not file. A missed item shows up again in the next meeting; a duplicate costs someone a triage
decision and teaches them to ignore your cards.

## Scope filter

A meeting notes account often captures a whole calendar, including things that are nobody's business but the account
owner's. **A meeting is in scope only if it is company business.** Signals, in order of reliability:

- `is_workspace_visible="false"` is a strong signal the meeting is personal. Default to skipping unless the content is
  unmistakably company work.
- A meeting with no participant from the configured company domains (`scope.company_participant_domains`) and no
  company subject matter is out of scope.
- Anything that reads as medical, financial, legal-personal, family, or recruitment of a named individual is out of
  scope even if it is workspace-visible (`scope.out_of_scope_topics`). If it would embarrass someone to find it in a
  shared issue tracker, it does not go in one.

A note someone else captured (`captured_by_me="false"`) is judged on exactly these terms and no others: not more in
scope for being a teammate's, not less for not being the account owner's. What it will not be is a second copy of a
meeting already handled, so collapse duplicates first.

When genuinely unsure, skip it and note the uncertainty in the state file. A missed issue costs a follow-up; a
personal appointment filed in a shared tracker cannot be unseen.

## One meeting, several captures

**A meeting id is not a meeting.** Meeting-notes tools may file one note per *capturer*, so a standup that two people
both recorded comes back as two notes: different ids, same title, same start time. Both are new to the state file.
Processing both files the same card twice and the reviewer cannot tell which duplicate is real.

- Same **title** and same **start time** (to the minute) means one meeting, however many ids it has.
- Pick **one note to work from** - normally the one with a summary worth reading - and ignore the rest.
- Record **every id** on one state entry (`ids: [processed, sibling...]`), so a later run does not rediscover the
  sibling as new work. The one you processed goes first.
- Never merge two meetings that merely share a title. A recurring standup has the same title every day; the start
  time makes them the same meeting.

## Domain lenses

- **Trackable vs said**: an issue needs an outcome someone could close. "We should think about pricing" is not one;
  "Draft three pricing tiers for the board meeting" is.
- **One issue, one outcome**: if a proposal needs "and" to describe it, it is two issues or it is a project.
- **Owner implied, not invented**: capture who the meeting expected to do it; never assign someone who was not named.
- **Decision vs discussion**: record decisions as issues only when they need follow-up work. A decision already
  carried out is not a ticket.
- **Duplicate before new**: search before proposing, and again before filing an approved item. A link to the existing
  issue is a better outcome than a second ticket.
- **Progress is not work**: a status report generates no issues, which is why a standup usually generates none.
- **Recurring-meeting drag**: standups repeat topics. An item mentioned three days running is one issue, not three.
- **Consent and exposure**: a tracker issue is durable and widely readable. Do not move personal, medical or
  individual-performance content into it.
- **Faithful, not creative**: the issue says what the meeting said. If you are adding requirements nobody voiced,
  stop and propose less.
- **Silence is a valid result**: zero issues from a meeting is the common, correct outcome.
- **Cost of a false positive**: a wrong issue costs someone a triage decision and some trust. Propose the ones you
  would defend.

## Output bar

A good card is one a reviewer can decide on in fifteen seconds without opening anything.

Not done: fields run together with no line breaks; a card with no `Existing search:` line; a proposal that describes
finishing or continuing existing work; a card that says "action item from standup" with no quote; a title that
restates the meeting name; several unrelated items bundled into one card; an issue created before a decision was
recorded by the host.
