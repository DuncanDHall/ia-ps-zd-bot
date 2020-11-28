# Patron Services Team Diffbot

This is a process that checks two mailbox folders and identifies messages forwarded into one but 
not the other. It is currently set up to track differences between the stream of emails forwarded
to our Zendesk account and the stream of tickets created within Zendesk.

## Implementation

1. Email incoming to the diffbot mailbox is filtered into two folders: `FROM_ZENDESK` and
`FROM_SUPPORT_ACCOUNTS`

2. Within Zendesk there is a trigger that forwards ticket details whenever a ticket is created to
the address specified in `diffbot/.env` (diffbot mailbox).

3. Every email address that forwards to Zendesk also forwards to the diffbot mailbox.

4. Email is compared between these two folders at regular time intervals

5. Unmatched emails are forwarded back to Zendesk (through the whitelisted diffbot address)

6. Zendesk tags emails coming from the diffbot address as `from-diffbot`
