# Streamly web player: user stories (fictional service, English)

Synthetic spec for the Coverlens OTT web domain. Fictional service, web only. Built from public knowledge of web streaming (HLS, DASH, EME/DRM). No data from any real operator.

## US-01 Sign in and out

As a viewer, I want to sign in and out so that my account and viewing history stay private.

Acceptance criteria:

- **US-01.AC1** A user with valid credentials signs in and lands on the home page.
- **US-01.AC2** Invalid credentials show an error message and do not create a session.
- **US-01.AC3** After 5 consecutive failed attempts the account is locked for 15 minutes.
- **US-01.AC4** Signing out ends the session and returns to the signed-out home page.

## US-02 Catalogue search

As a viewer, I want to search the catalogue so that I can find something to watch.

Acceptance criteria:

- **US-02.AC1** Search returns titles matching the query, ranked by relevance.
- **US-02.AC2** A search with no matches shows an empty-state message.
- **US-02.AC3** Titles unavailable in the user's region are hidden from results.
- **US-02.AC4** Search suggestions appear after the user has typed 3 characters.

## US-03 Start on-demand playback

As a viewer, I want to start a title on demand so that I can watch it right away.

Acceptance criteria:

- **US-03.AC1** Selecting a title starts playback in the player and shows a loading state until the first frame is rendered.
- **US-03.AC2** A signed-out user who selects a title is prompted to sign in and returns to the title afterwards.
- **US-03.AC3** Playback starts at the saved position if one exists, otherwise at the beginning.
- **US-03.AC4** When playback ends, the next episode is offered with a 10 second countdown.

## US-04 Live playback

As a viewer, I want to watch live channels so that I can follow events as they happen.

Acceptance criteria:

- **US-04.AC1** A live channel starts playback at the live edge.
- **US-04.AC2** The user can pause live playback and resume from the paused point within the DVR window.
- **US-04.AC3** Seeking beyond the live edge is not possible.
- **US-04.AC4** When a live event ends, the player shows an end-of-event message.

## US-05 Player controls

As a viewer, I want standard player controls so that I can control what I watch.

Acceptance criteria:

- **US-05.AC1** Play and pause toggle playback with the space key and with the on-screen button.
- **US-05.AC2** Clicking the progress bar moves playback to that position (on-demand titles only).
- **US-05.AC3** Volume and mute state persist across titles within the same session.
- **US-05.AC4** Fullscreen can be entered and exited with the button and with the Escape key.

## US-06 Adaptive quality

As a viewer, I want the video quality to adapt so that playback stays smooth on my connection.

Acceptance criteria:

- **US-06.AC1** Quality adapts automatically to available bandwidth without stopping playback.
- **US-06.AC2** The user can select a fixed quality, and the selection is kept until changed.
- **US-06.AC3** Qualities above the limit of the user's plan are disabled in the quality menu.
- **US-06.AC4** On a slow network playback drops to a lower quality instead of stalling.

## US-07 Subtitles and audio tracks

As a viewer, I want to choose subtitles and audio so that I can watch in my preferred language.

Acceptance criteria:

- **US-07.AC1** The user can turn subtitles on and choose a language from the available list.
- **US-07.AC2** The user can switch the audio track without restarting playback.
- **US-07.AC3** The subtitle and audio choices are remembered for the next title.
- **US-07.AC4** Titles with no subtitles hide the subtitle control.

## US-08 Plan entitlement

As a subscriber, I want access to match my plan so that I get what I pay for.

Acceptance criteria:

- **US-08.AC1** A user with an active plan can play all titles included in the plan.
- **US-08.AC2** A signed-in user without a plan sees a subscribe prompt for paid titles.
- **US-08.AC3** A user whose plan has expired loses access on the expiry date and sees a renewal prompt.
- **US-08.AC4** Free titles are playable by any signed-in user without a plan.

## US-09 Regional availability

As the service operator, I want titles restricted by region so that licensing terms are respected.

Acceptance criteria:

- **US-09.AC1** A user in a licensed region can play the title.
- **US-09.AC2** A user outside the licensed region sees a 'not available in your region' message.
- **US-09.AC3** The region is determined from the network location, not from the account country.
- **US-09.AC4** A user connecting through a detected proxy or VPN is treated as outside the licensed region.

## US-10 Concurrent streams

As the service operator, I want to limit concurrent streams per plan so that accounts are not shared widely.

Acceptance criteria:

- **US-10.AC1** A plan allows streams up to its stream limit at the same time.
- **US-10.AC2** Starting a stream above the limit is blocked with a message that names the limit.
- **US-10.AC3** Closing a stream frees a slot within 60 seconds.
- **US-10.AC4** The stream limit applies across browsers for the same account.

## US-11 Error handling and recovery

As a viewer, I want playback to recover from problems so that a bad connection does not ruin what I am watching.

Acceptance criteria:

- **US-11.AC1** If the network drops during playback the player shows a reconnecting state.
- **US-11.AC2** Playback resumes automatically when the network returns within 30 seconds.
- **US-11.AC3** If the network does not return within 30 seconds an error with a retry button is shown.
- **US-11.AC4** A failed license request shows a playback error with an error code and does not retry in a loop.

## US-12 DRM and supported browsers

As the service operator, I want protected content to play only through supported DRM so that content owners' requirements are met.

Acceptance criteria:

- **US-12.AC1** Safari plays protected HLS content using FairPlay.
- **US-12.AC2** Edge plays protected DASH content using PlayReady.
- **US-12.AC3** Chrome and Firefox play protected DASH content using Widevine.
- **US-12.AC4** A browser without a supported DRM shows an unsupported-browser message instead of a black screen.

## US-13 Continue watching

As a viewer, I want to continue where I left off so that I do not lose my place.

Acceptance criteria:

- **US-13.AC1** Playback progress is saved at regular intervals while watching.
- **US-13.AC2** A title watched past 95% is marked as watched and removed from Continue Watching.
- **US-13.AC3** Continue Watching lists titles ordered by most recently watched.
- **US-13.AC4** Progress is shared across browsers for the same account.
