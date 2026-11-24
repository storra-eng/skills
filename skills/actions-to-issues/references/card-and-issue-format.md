# Cards, issues and duplicates

## The approval card

The card is read in a chat client, where **a wall of unbroken text is unreadable**. Use this exact structure, with real
line breaks and blank lines between blocks:

```
*<proposed issue title>*

<two to four lines of description: the context, the specific ask, and the outcome
that would close it>

*Card:* <card id>   (<meeting id>-<n>)
*Source:* <meeting title>, <date>[, <meeting link, only when the note source returned one>]
*Quote:* "<the line from the notes that justifies this>"
*Existing search:* <what you searched for and what you found, or "no match">

<the tracker adapter's categorisation lines - for Linear:>
*Project:* <project name> - <one clause on why, or "best fit: <why nothing fits better>">
*Labels:* <one or more labels from the config>
*Priority:* <Urgent / High / Medium / Low, with the words from the notes that set it, or "none">
*Assignee:* <the person the meeting named, or "none">
```

The block above the categorisation lines is the same for every tracker. The categorisation lines come from
`references/tracker-<tracker>.md`, in its order: Jira adds issue type and components, GitHub names a repository and
a milestone and has no priority line.

- The title goes on its own line and names an **outcome**, not a conversation ("Rate-limit the outreach send path",
  not "Discuss outreach limits").
- The quote is verbatim from the notes. It is what lets a reviewer decide without opening anything.
- The search line proves you did step 1 of the New-work test. A card without it should be rejected.
- The categorisation lines are how the reviewer approves the issue's **categorisation** along with the item. Fill them
  from the config when you write the card, not later. If the reviewer disagrees with a project they reject the card.
- Each card is self-contained: title, description, meeting, date and justifying quote. "See the meeting notes" is not
  a proposal.
- Card ids: the **full** meeting id, a hyphen, and `n` counting from 1 within the meeting (`<meeting id>-<n>`).
  The meeting id is everything before the final hyphen. Truncated ids are not unique, and the filing run needs the
  full meeting id to build the source link without reading anything but the approved card.
- Chat clients may render markdown differently; keep the field labels and order regardless.

## Categorisation

The rules below use Linear's field names; the adapter maps them (a GitHub repository is the "project").

- **Project: always.** Pick from the config by the surface the work lands in. If nothing fits well, propose the
  closest and say "best fit"; never create a project. Pass it in the form the adapter's "Calls" table gives (Linear
  id, Jira key, GitHub owner/name).
- **Labels: at least one**, from the config only, unless the adapter's card line allows `none` (Jira). Never create
  a label.
- **Priority: only when the meeting gave a reason** - a date, "urgent", "blocker", "this week". Otherwise `none`.
  Never default to Medium. A tracker without priority (GitHub) gets the reason in the description instead.
- **Assignee: only someone the meeting named as doing it**, by id (or login) from the config. Otherwise `none`. Never
  "me": the tracker session may belong to whoever authorised the integration, not the person the meeting meant.

## Writing the issue (FILE phase)

A created issue has:

- a title that names the outcome, exactly as approved;
- a description with the context, the specific ask, and a link back to the source meeting using the config's
  the link on the card's *Source:* line when there is one (Fireflies `transcript_url`, Fathom `share_url`),
  otherwise the config's `issue.link_template` (the meeting id comes from the approved card's id), as a markdown link `[<meeting title>, <date>](<url>)`. Meeting-note share links are often
  "anyone with the link can view", so the link is a convenience for whoever triages, not licence to paste more of the
  note than the justifying quote;
- the attribution line from `issue.attribution_template`, last;
- the categorisation **from the approved card**, exactly as approved.

Read the create response as the adapter says (Linear: it must carry a project id). A field that did not match can be
dropped silently with a success response. **Do not call the write tool a second time to fix it** - record it in the
state file and report it. Pass the ids correctly the first time and the problem does not arise.

## Duplicates: re-search before filing

The search you ran when proposing is stale by the time you file. Approval and filing are at least one run apart, and
in that gap someone else can file the same item.

Immediately before creating an approved issue, search again for the topic (not a title match; the other issue will not
be worded like yours). Look at issues created since the card was posted first.

- **Nothing covers it**: create the issue.
- **An existing issue plainly has the same outcome**: do not create one. Add a comment to it. The body gives the source
  meeting link, the justifying quote only if the existing issue lacks that context, and ends with the attribution line
  noting it was approved as a duplicate of this issue. Record the **existing** key on the meeting's state entry.
- **Unsure whether it covers it**: create the issue and name the possible overlap in its description. A human approved
  this item; burying it in a comment on something only loosely related leaves nothing to find, while a possible
  duplicate is visible and cheap to close.
- Put the attribution line last, and do not quote any other approval id in the body.
