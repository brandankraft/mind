#!/usr/bin/env python3
"""
Inject clickable "play song" chips into specific chapter HTML files (web only).
The PDF/EPUB versions don't get these -- they stay clean.

Each entry: (filename, marker_text_substring, source_album_slug, song_title, album_title)
Optional 6th element: close_tag string (default '</p>'). Chip is inserted right after
the first occurrence of close_tag following the marker. Useful when the marker is
inside a blockquote or other structure where the desired insertion point is not a </p>.

The chip identifies the song by (source_album_slug, song_title) -- NOT by a track
index. Clicking it calls window.bookMusicPlayChip(sourceAlbum, title), which
resolves the song's CURRENT position in the All Music album at click time, loads
it into the site-wide bottom bar player, starts playback, and opens the lyrics
panel. Because the chip carries identity rather than position, inserting songs
anywhere in the All Music arc never invalidates a chip -- no re-indexing needed.
"""
import os
import re
import sys

SONGS = [
    # Preface (Campless): "No Fence Holds Me" at the close of the Campless
    # section -- the song is that section placed as a life. The campless
    # thesis: not Calvinist, not Reformed, not anything, because no fence
    # holds all of what he believes. Lands right after "campless is the only
    # honest place to stand when the truth doesn't fit inside any fence."
    (
        'preface.html',
        'campless is the only honest place to stand',
        "outside-the-camp",
        "No Fence Holds Me",
        "Outside the Camp",
    ),
    # Appendix A1 (Made Sin): "Made Sin" after the paragraph arguing Paul used
    # the strongest possible language -- hamartia, the noun for sin itself, not
    # the technical phrase for a sin offering -- because he meant the strongest
    # reading. The song is exactly that doctrine: Christ made sin in the body,
    # bearing the consequence, never the rebellion.
    (
        'appendix-a1.html',
        'strongest language available in his vocabulary',
        "outside-the-camp",
        "Made Sin",
        "Outside the Camp",
    ),
    # Chapter 19 (No Common Grace): "The Sharpest Sword" right after the Darth
    # Gill aside -- B's old predestinarian.net forum handle, John Gill with a
    # Sith honorific. The song is the confession of those forum years: sharp,
    # relentless, right on the doctrine and cruel in the delivery.
    (
        'chapter-19.html',
        'John Gill the Particular Baptist with a Sith honorific bolted on',
        "outside-the-camp",
        "The Sharpest Sword",
        "Outside the Camp",
    ),
    # Appendix A10 (On Heresy Hunting): "A Man Named Heretic" after the
    # "Slapping labels" paragraph -- the hunter condemns the label instead of
    # engaging the argument: "Hyper-calvinist," "Compromiser," "Tolerant." The
    # song is the comic story of being named all of them, often by one man.
    (
        'appendix-a10.html',
        'condemns the label instead of engaging the argument.',
        "outside-the-camp",
        "A Man Named Heretic",
        "Outside the Camp",
    ),
    # Acknowledgments (Bob Higby): "One Doctrine at a Time" after the Bob Higby
    # paragraph -- "I named the system. He gave me the pieces." The song is the
    # whole theology built from scavenged parts, one doctrine at a time.
    (
        'acknowledgments.html',
        'I named the system. He gave me the',
        "outside-the-camp",
        "One Doctrine at a Time",
        "Outside the Camp",
    ),
    # About This Book: "Ditch the Garbage!" after the opening paragraph --
    # "building something I didn't know had a name." The song is that exact
    # moment: the raw refusal of churchianity, the no before the vocabulary,
    # twenty years before the framework arrived to name what was refused.
    (
        'about.html',
        'and a lot of late nights',
        "ditch-the-garbage",
        "Ditch the Garbage!",
        "Ditch the Garbage!",
    ),
    # Chapter 26 (The Canon): "Six Easy Steps" right after the line that
    # crystallizes the Rome-attack -- "The Bible is Scripture because the
    # church says so." The song is that exact move played sardonically:
    # how to bury the Bible under a council, flatten the canon, weaponize
    # or dismiss the antilegomena.
    (
        'chapter-26.html',
        'The Bible is Scripture because the church says so.',
        "ditch-the-garbage",
        "Six Easy Steps",
        "Ditch the Garbage!",
    ),
    # Chapter 2: "Every Frame" right after the filmstrip metaphor closes --
    # "He is the Filmmaker. We are the characters. And time is the filmstrip."
    # The song is the metaphor in audio form: every frame already seen at once.
    (
        'chapter-02.html',
        'And time is the filmstrip.',
        "still-the-first-time",
        "Every Frame",
        "Still the First Time",
    ),
    # Chapter 15: "Every Frame" right after the chapter's punchline declaring
    # the elect were justified before they sinned, payment before the debt.
    # Justification from eternity is exactly what the song is about.
    (
        'chapter-15.html',
        'the payment was made before the debt existed.',
        "still-the-first-time",
        "Every Frame",
        "Still the First Time",
    ),
    # Appendix L: "I'm a Preacher" at the close of section I "The Last Sermon"
    # -- Holloway has just preached his denunciation, gone home, and started
    # writing "You must never shrink from naming the wolves" before his heart
    # stops at his desk. The song is the man-as-credential portrait, lands
    # on the dying-at-the-pulpit moment.
    (
        'appendix-l.html',
        'The tea went\ncold.',
        "still-the-first-time",
        "I'm a Preacher",
        "Still the First Time",
    ),
    # Appendix A5 (On Plural Eldership vs. the Single Pastor): "I'm a Preacher"
    # at the close of the section that diagnoses the Baptist-pope single-pastor
    # model. The song is the costume-eats-the-man critique in audio form.
    (
        'appendix-a5.html',
        'are willing to admit.',
        "still-the-first-time",
        "I'm a Preacher",
        "Still the First Time",
    ),
    # Appendix A5 (On Clerical Titles): "You are a Priest" at the close of the
    # section that strips the Reverend/Father/Master titles and affirms equal
    # standing -- "all are brethren, all stand in the same righteousness."
    # The song is that section as anthem.
    (
        'appendix-a5.html',
        'name. Not ours.',
        "still-the-first-time",
        "You are a Priest",
        "Still the First Time",
    ),
    # Appendix N (Costume 6): "I'm a Preacher" at the close of the Damage
    # paragraph -- the credential eating the man, the pulpit as gate. The
    # song is the diagnosis in audio form.
    (
        'appendix-n.html',
        'cannot read Scripture without expert\nmediation.',
        "still-the-first-time",
        "I'm a Preacher",
        "Still the First Time",
    ),
    # Appendix N (Costume 7: Institutional Church Model): "You are a Priest"
    # at the close of the Framework correction paragraph -- the body of Christ
    # is the gathered saints, not the institution. Moved here from Costume 6
    # to give "I'm a Preacher" (Costume 6 Damage close) breathing room.
    (
        'appendix-n.html',
        'serves the body or feeds on the\nbody.',
        "still-the-first-time",
        "You are a Priest",
        "Still the First Time",
    ),
    # Chapter 23: "You are a Priest" right after "You are in the body of
    # Christ by regeneration." -- the song's whole posture is "you are
    # already in, you are already a priest, no committee required."
    (
        'chapter-23.html',
        'You are in the body of Christ by regeneration.',
        "still-the-first-time",
        "You are a Priest",
        "Still the First Time",
    ),
    # Chapter 1: "What Plato Built" right after the Plato/Republic paragraph
    # that names the law of Plato and Augustine importing it. The song is
    # that paragraph rendered as music. Marker is short to avoid pandoc wrap.
    (
        'chapter-01.html',
        'sixteen centuries of Christian theology.',
        "still-the-first-time",
        "What Plato Built",
        "Still the First Time",
    ),
    # Chapter 13: "What Plato Built" inside "## The Law of Plato" right after
    # the opening declaration of the law's name. Short marker avoids the em
    # tag and pandoc line wrap.
    (
        'chapter-13.html',
        'keep saying it until it sticks',
        "still-the-first-time",
        "What Plato Built",
        "Still the First Time",
    ),
    # Appendix I: "What Plato Built" right after the lineage diagram's closing
    # sentence. The song is the lineage rendered in audio form.
    (
        'appendix-i.html',
        'It lays a new one.',
        "still-the-first-time",
        "What Plato Built",
        "Still the First Time",
    ),
    # Appendix N: "What Plato Built" near the top, right after the
    # introduction's closing sentence. Press play before reading the catalogue
    # -- the song is the diagnosis in 4 minutes.
    (
        'appendix-n.html',
        'The Author handles the rest.',
        "still-the-first-time",
        "What Plato Built",
        "Still the First Time",
    ),
    # Chapter 3: "Bit From God" song chip after the "I say 'bit from God.'" declaration
    (
        'chapter-03.html',
        'I say \u201cbit from God.\u201d',
        "sweet-release",
        "Bit From God",
        "Sweet Release",
    ),
    # Chapter 23: "Every One of You" song chip right before "Church Membership Is a Formality"
    (
        'chapter-23.html',
        'They shouldn\u2019t be.',
        "sweet-release",
        "Every One of You",
        "Sweet Release",
    ),
    # Chapter 30: "Break the Throne" after "I thought I was contending for the faith."
    (
        'chapter-30.html',
        'thought I was contending for the faith.',
        "sweet-release",
        "Break the Throne",
        "Sweet Release",
    ),
    # Chapter 30: "Enough for Me" after the lyric quote in "The Song That Says It Better"
    (
        'chapter-30.html',
        'then brother, that\u2019s enough for me.',
        "break-the-cage",
        "Enough for Me",
        "Break the Cage",
    ),
    # Chapter 1: "A Thought in the Mind of God" right below the blockquoted "sentence"
    (
        'chapter-01.html',
        'personal covenants of love.',
        "sweet-release",
        "A Thought in the Mind of God",
        "Sweet Release",
        '</blockquote>',
    ),
    # Appendix G: "Bit From God" after the "rendering engine / bit of information" paragraph
    (
        'appendix-g.html',
        'was produced by random\nprocesses.',
        "sweet-release",
        "Bit From God",
        "Sweet Release",
    ),
    # Appendix H: "Bit From God" after the double-slit experiment paragraph
    (
        'appendix-h.html',
        'like a particle when watched and like a\nwave when not watched.',
        "sweet-release",
        "Bit From God",
        "Sweet Release",
    ),
    # Chapter 27: "O Lamb of God" at the end of the historicism section
    (
        'chapter-27.html',
        'Author hasn\u2019t written \u201cThe End\u201d yet.',
        "from-pride-to-praise",
        "O Lamb of God",
        "From Pride to Praise",
    ),
    # Chapter 14: "Small and Great" before "Degrees of Punishment, Not Degrees of Grace"
    (
        'chapter-14.html',
        'infinitely covered by the blood of\nChrist.',
        "sweet-release",
        "Small and Great",
        "Sweet Release",
    ),
    # Epilogue: "The Man Behind the Glass" after "I need to tell you what happened to me..."
    (
        'epilogue.html',
        'I need to tell you what happened to me while I was writing this.',
        "sweet-release",
        "The Man Behind the Glass",
        "Sweet Release",
    ),
    # Epilogue: "A Thought in the Mind of God" after "I am becoming aware, slowly, that I am a thought."
    (
        'epilogue.html',
        'I am becoming aware, slowly, that I am a thought.',
        "sweet-release",
        "A Thought in the Mind of God",
        "Sweet Release",
    ),
    # Appendix L: "The Gatekeeper" at the close of The Gatekeepers parable.
    # The song IS the parable's portrait of Holloway -- companion piece, lands
    # on the final "scars in his hands" line.
    (
        'appendix-l.html',
        'And the gate was a man with scars in his hands.',
        "ditch-the-garbage",
        "The Gatekeeper",
        "Ditch the Garbage!",
    ),
    # Appendix L: "Glass Cathedral" at the close of section VI "The Filmstrip"
    # -- the moment "I never knew you" lands and the cathedral breaks for
    # Holloway. The song is the soundtrack of that shatter. (Moved here from
    # the parable close, which now belongs to The Gatekeeper.)
    (
        'appendix-l.html',
        '(Matthew 7:23).',
        "sweet-release",
        "Glass Cathedral",
        "Sweet Release",
    ),
    # Chapter 20: "Your Knowledge Won't Save You" after the law-vs-Christ rhetorical close
    (
        'chapter-20.html',
        'That\u2019s what changes a person. Not the law. Christ.',
        "break-the-cage",
        "Your Knowledge Won't Save You",
        "Break the Cage",
    ),
    # Chapter 15: "It is Finished!" at the close of the "It Is Finished Means
    # Finished" section. Moved off the previous section close to give Every
    # Frame breathing room (was stacked one paragraph apart).
    (
        'chapter-15.html',
        'God\u2019s mind is the\none that matters.',
        "in-the-little-things",
        "It is Finished!",
        "In the Little Things",
    ),
    # Chapter 15: "Preserved in His Grace" after the line about preservation while ignorant
    (
        'chapter-15.html',
        'were preserved even while ignorant of Him.',
        "in-the-little-things",
        "Preserved in His Grace",
        "In the Little Things",
    ),
    # Chapter 6: "Crown of Thorns" mid-Infinite-Loop, after "The character dies. The Author keeps writing."
    (
        'chapter-06.html',
        'The character\ndies. The Author keeps writing. And they are the same Person.',
        "sweet-release",
        "Crown of Thorns",
        "Sweet Release",
    ),
    # Chapter 21: "Sugar Water" at the close of "Rebuke the Imposers" -- the song
    # names the very thing the section rebukes (gatekeepers, boxes, creeds-as-cages)
    (
        'chapter-21.html',
        'they become the yoke of bondage that Christ died to\nbreak.',
        "break-the-cage",
        "Sugar Water",
        "Break the Cage",
    ),
    # Chapter 21: "Head Over Heels" after "...because you love the One who did everything for you."
    (
        'chapter-21.html',
        'because you love the One who did everything for you.',
        "sweet-release",
        "Head Over Heels",
        "Sweet Release",
    ),
    # Chapter 18: "Pepper in the Wind" at end of "The Danger of Progressive Sanctification"
    (
        'chapter-18.html',
        'Not your upward trajectory. Christ. And Christ is\nfinished.',
        "sweet-release",
        "Pepper in the Wind",
        "Sweet Release",
    ),
    # Appendix A4: "Ready to Glow" at the close of "On the Head and Heart Dichotomy"
    (
        'appendix-a4.html',
        'The head and the heart are one. Always were.',
        "break-the-cage",
        "Ready to Glow",
        "Break the Cage",
    ),
    # Appendix A1: "Stop Puttin' God in a Box" at the close of "On the Mud, the Spit, and the Lawgiver"
    (
        'appendix-a1.html',
        'Stop building\nboxes. Look at Him.',
        "break-the-cage",
        "Stop Puttin\u2019 God in a Box",
        "Break the Cage",
    ),
    # Appendix A5: "Stop Puttin' God in a Box" at the close of "On Creeds and Confessions"
    (
        'appendix-a5.html',
        'Because no camp has everything.',
        "break-the-cage",
        "Stop Puttin\u2019 God in a Box",
        "Break the Cage",
    ),
    # Chapter 30: "Tolerance" at the close of "The Confusion, Not the Rebellion" --
    # after Brandan's own confession that he's done exactly what the song condemns.
    (
        'chapter-30.html',
        'I know I have. And it grieves me.',
        "break-the-cage",
        "Tolerance",
        "Break the Cage",
    ),
    # Chapter 21: "Study to be Quiet" at the close of the "Study to Be Quiet" section
    (
        'chapter-21.html',
        'Author write whatever chapter He wants with the life He gave.',
        "break-the-cage",
        "Study to be Quiet",
        "Break the Cage",
    ),
    # Appendix A10: "Holy Trollers" after Brandan's admission he's been both
    # contender and heresy hunter
    (
        'appendix-a10.html',
        'I know the difference because I have been both.',
        "from-pride-to-praise",
        "Holy Trollers",
        "From Pride to Praise",
    ),
    # Appendix A10: "Words Can Draw a Line" at the close of the Judges 12
    # Shibboleth retelling (first paragraph of "On Shibboleths").
    # Marker uses the rendered italics + word-wrap form; default close_tag '</p>'
    # places the chip right after the paragraph ends.
    (
        'appendix-a10.html',
        'Over how they <em>said</em>\nit.',
        "in-the-little-things",
        "Words Can Draw a Line",
        "In the Little Things",
    ),
    # Appendix A10: "Our Pride Monster" after Brandan's confession in
    # "On Using Theology as a Weapon"
    (
        'appendix-a10.html',
        'And I did it all in the\nname of defending the Gospel.',
        "from-pride-to-praise",
        "Our Pride Monster",
        "From Pride to Praise",
    ),
    # Appendix A5: "Are You Called to Preach?" at the opening declaration of "On Ordination"
    (
        'appendix-a5.html',
        'The gifting is the\nsubstance.',
        "in-the-little-things",
        "Are You Called to Preach?",
        "In the Little Things",
    ),
    # Appendix A5: "Deeper Than the Words We Speak" in "On Evangelism and Soul Winning"
    (
        'appendix-a5.html',
        'It\nis a proclamation of accomplished salvation.',
        "in-the-little-things",
        "Deeper Than the Words We Speak",
        "In the Little Things",
    ),
    # Appendix A9: "Prayer Arithmetic" after the intro sentence of "On the Lord's Prayer"
    (
        'appendix-a9.html',
        'The phrases map to the\nframework:',
        "break-the-cage",
        "Prayer Arithmetic",
        "Break the Cage",
    ),
    # Appendix A9: "Your Knowledge Won't Save You" at the opening of "On Judas"
    (
        'appendix-a9.html',
        'And the strongest test case\nfor the framework.',
        "break-the-cage",
        "Your Knowledge Won't Save You",
        "Break the Cage",
    ),
    # Appendix A10: "The Zealot's Quest" in "On Gatekeeping" after the root-sin declaration
    (
        'appendix-a10.html',
        'the authority to determine who belongs to Christ and who doesn\u2019t.',
        "in-the-little-things",
        "The Zealot's Quest",
        "In the Little Things",
    ),
    # Chapter 23: "Walked Out Free" in "How I Got Here" after Brandan references
    # the church-hurt story that became article, song, podcast, and this chapter
    (
        'chapter-23.html',
        'And it became one of the\nreasons I\u2019m writing this chapter.',
        "in-the-little-things",
        "Walked Out Free",
        "In the Little Things",
    ),
    # Appendix A10: "The Thief" at the close of the opening paradigm paragraph
    # in "On the Thief on the Cross"
    (
        'appendix-a10.html',
        'The thief exposes every\ngatekeeper.',
        "from-pride-to-praise",
        "The Thief",
        "From Pride to Praise",
    ),
    # Acknowledgments: "On a Leash" after the "Iron sharpens iron. Even when the iron
    # draws blood." paragraph -- the song is the posture, the Acknowledgments is what
    # the posture produced: naming the people who hurt him with thank-you instead of a
    # rebuttal, lifting Christ instead of naming enemies.
    (
        'acknowledgments.html',
        'Iron\nsharpens iron. Even when the iron draws blood.',
        "break-the-cage",
        "On a Leash",
        "Break the Cage",
    ),
    # Chapter 5: "All Things" after the intro sentence that predestination is
    # intimidating
    (
        'chapter-05.html',
        'excited about\nfootball.',
        "from-pride-to-praise",
        "All Things",
        "From Pride to Praise",
    ),
    # Chapter 5: "Your Sovereign Will Stands Firm" after the equal-ultimacy declaration
    (
        'chapter-05.html',
        'Both are the positive, active will of\nGod, planned from the end to the beginning.',
        "from-pride-to-praise",
        "Your Sovereign Will Stands Firm",
        "From Pride to Praise",
    ),
    # Preface: "In the Little Things" at the close of "The Man Without Credentials"
    # -- where the shepherds / fishermen / tax collectors frame lands
    (
        'preface.html',
        "That\u2019s who I am. And this is the book I wasn\u2019t supposed to write.",
        "in-the-little-things",
        "In the Little Things",
        "In the Little Things",
    ),
    # Chapter 29: "Still the First Time" immediately below the tombstone figure
    (
        'chapter-29.html',
        'Our shared tombstone, made 2025',
        "still-the-first-time",
        "Still the First Time",
        "Still the First Time",
        '</figure>',
    ),
    # Appendix A6: "Still the First Time" partway through "On the Covenant Companion"
    # (after the ontological-register paragraph, before the twin-covenant resolution)
    (
        'appendix-a6.html',
        'is not bound by the same terminus.',
        "still-the-first-time",
        "Still the First Time",
        "Still the First Time",
    ),
    # Appendix A11: "Rise Above" at the close of "On Being Hurt by the Church".
    # Disambiguating marker because the phrase appears twice in the chapter --
    # include the preceding trio so we match the church-hurt occurrence, not the
    # earlier forgiveness-section one.
    (
        'appendix-a11.html',
        'The evil was real. The purpose was also real. And the purpose was bigger\nthan the pain.',
        "break-the-cage",
        "Rise Above",
        "Break the Cage",
    ),
    # Chapter 30: "Let it be Love" lands right after the risk-asymmetry punchline
    # "If I must err, let it be the error that costs me, not the one that costs
    # him." -- the song is that sentence set to music.
    (
        'chapter-30.html',
        'not the one that costs him.',
        "in-the-little-things",
        "Let it be Love",
        "In the Little Things",
    ),
    # Appendix O: "Your Knowledge Won't Save You" after the framework's
    # soteriology distilled to one sentence: "It's not what you know. It's not
    # even who you know. It's who knows you." -- the song is that exact thesis.
    (
        'appendix-o.html',
        'who\nknows you.',
        "break-the-cage",
        "Your Knowledge Won't Save You",
        "Break the Cage",
    ),
    # Appendix A7: "He Goes First" after "That is not symmetry with the wife's
    # submission. That is a heavier weight." -- the song is the wife's voice
    # answering the husband who goes first in love and dying.
    (
        'appendix-a7.html',
        'That is a heavier weight.',
        "still-the-first-time",
        "He Goes First",
        "Still the First Time",
    ),
    # Chapter 15: "Cover Me" after the Active Obedience paragraph -- the song is
    # imputed righteousness sung ("Cover me in mercy I could never earn... see in
    # me what I could never be alone"), and the marker line literally says
    # "covering every sin from eternity to eternity."
    (
        'chapter-15.html',
        'Perfect and complete, covering every sin from',
        "sweet-release",
        "Cover Me",
        "Sweet Release",
    ),
    # Appendix A11: "The Chamber" at the close of "On Fear of Death". The song is
    # the deathbed stripping ("All the strength you thought was yours falls like
    # dust across the floor") and Christ reaching in -- placed before A Final Word.
    (
        'appendix-a11.html',
        'dreading it. He was eager for it.',
        "sweet-release",
        "The Chamber",
        "Sweet Release",
    ),
    # Appendix E: "Every Room" at the close of "The Theological Connection". The
    # song's bridge ("a Voice that knew my name before I ever knew") is firmware-
    # level regeneration -- the "hidden part" Psalm 51:6 names.
    (
        'appendix-e.html',
        'the architecture David was already',
        "sweet-release",
        "Every Room",
        "Sweet Release",
    ),
    # Epilogue: "Sweet Release" (title track) replaces the prior YouTube embed.
    # Anchored to "And I intend to stay that way." -- right after "I am free.
    # A sweet release from the captivity of the institution."
    (
        'epilogue.html',
        'intend to stay that way.',
        "sweet-release",
        "Sweet Release",
        "Sweet Release",
    ),
    # Chapter 30: "Your Knowledge Won't Save You" -- mandatory placement; the
    # chapter literally cites this song by name as an article Brandan wrote
    # years ago. Lands after "I believed every word of it then. I still do."
    (
        'chapter-30.html',
        'I believed every word of it then. I still do.',
        "break-the-cage",
        "Your Knowledge Won't Save You",
        "Break the Cage",
    ),
    # Chapter 30: "Has Jesus Been Lost in Your TULIP?" at the close of the
    # "Arminian in the TULIP Sweatshirt" section. Direct match -- the song's
    # title and the section's thesis are the same critique.
    (
        'chapter-30.html',
        'errors meet at the',
        "break-the-cage",
        "Has Jesus Been Lost in Your TULIP?",
        "Break the Cage",
    ),
    # Chapter 25: "Break the Cage" (title track) at the close of "TULIP in the
    # Framework". The song says "truth without grace is a cage in my mind" --
    # this section is where the framework reframes the five points.
    (
        'chapter-25.html',
        'what this book provides.',
        "break-the-cage",
        "Break the Cage",
        "Break the Cage",
    ),
    # Chapter 30: "Break the Cage" (title track) at the close of "What I See
    # Now" -- the autobiographical reflection on the rotten fruit and Brandan's
    # past. The song's "It took years for You to melt the iron in my spine,
    # so give me love for the ones still stuck in the grind" is that whole
    # section in lyric form.
    (
        'chapter-30.html',
        'Paul said it. Not me.',
        "break-the-cage",
        "Break the Cage",
        "Break the Cage",
    ),
    # Chapter 23: "From Movement to Monument" at the close of "What 'Church'
    # Actually Means". The section ends with the institutional model replacing
    # ekklesia; the song is the lament for that exact replacement.
    (
        'chapter-23.html',
        'model replaced.',
        "break-the-cage",
        "From Movement to Monument",
        "Break the Cage",
    ),
    # Chapter 23: "Preacher Bingo" at the close of "The One-Man Pulpit". The
    # song's whole concept (sitting in the pew listening to the same polemic
    # sermon) is a musical illustration of this critique.
    (
        'chapter-23.html',
        'Roman senate hearing than',
        "break-the-cage",
        "Preacher Bingo",
        "Break the Cage",
    ),
    # Appendix A11: "It's Enough!" at the close of "On Assurance". The song's
    # "don't need a date to prove His grace" is pure assurance-without-narrative.
    (
        'appendix-a11.html',
        'Indifference does not ask. Concern does.',
        "break-the-cage",
        "It's Enough!",
        "Break the Cage",
    ),
    # Appendix A11: "Joy Is Your Strength" at the close of "On Depression".
    # Nehemiah 8:10 in song form. Lands after the "He is not disappointed when
    # the dust does what dust does." line.
    (
        'appendix-a11.html',
        'He is not disappointed when the dust does what dust does.',
        "break-the-cage",
        "Joy Is Your Strength",
        "Break the Cage",
    ),
    # Appendix M: "Cannibal!" at the close of "The Reformation That Did Not
    # Finish". The song's "Christ was killed once for all, not so you could
    # watch the brethren fall" is the wound this appendix is treating.
    (
        'appendix-m.html',
        'for anyone honest',
        "break-the-cage",
        "Cannibal!",
        "Break the Cage",
    ),
    # Appendix M: "Stop Puttin' God in a Box" at the close of "Sola Fide -- Faith
    # Alone, Not Faith Plus Vocabulary". The song's "TULIP only shines in Jesus,
    # He's the center, not the chart" matches Sola Fide-without-vocabulary.
    (
        'appendix-m.html',
        'exactly what the Reformers accused Rome of doing.',
        "break-the-cage",
        "Stop Puttin\u2019 God in a Box",
        "Break the Cage",
    ),
    # Appendix L (A Vision of the Final State): "Small and Great" right after Mary Sutcliffe
    # is introduced -- the song honors the Mary Sutcliffes of the world, the
    # ones with no theology degree but a lived "Jesus loves me" faith.
    (
        'appendix-l.html',
        'meant it every time.',
        "sweet-release",
        "Small and Great",
        "Sweet Release",
    ),
    # Dedication: "I Just Want You to Understand" (the song's title line is
    # literally the dedication's text). Lands right after the dedication.
    (
        'dedication.html',
        'I just want you to understand.',
        "sweet-release",
        "I Just Want You to Understand",
        "Sweet Release",
    ),
    # Epilogue close: "I Just Want You to Understand" -- the personal letter
    # to Cole as the last word after "Grace and Peace, Brandan".
    (
        'epilogue.html',
        'Grace and Peace, Brandan',
        "sweet-release",
        "I Just Want You to Understand",
        "Sweet Release",
    ),
    # Chapter 30: "You Don't Know Me" right after Brandan lists the labels
    # critics have used (compromiser, arch-heretic, unbeliever). The song is
    # the dignified reply that lands in Christ, not in counter-attack.
    (
        'chapter-30.html',
        'compromiser more times than I can count',
        "sweet-release",
        "You Don't Know Me",
        "Sweet Release",
    ),
    # Chapter 24: "Tender and Strong" at the close of the "Tenderness" section.
    # The song narrates the tenderness Paul's restriction never touched -- the
    # wider ministry where mercy, encouragement, and care happen.
    (
        'chapter-24.html',
        'where most of the actual ministry happens.',
        "still-the-first-time",
        "Tender and Strong",
        "Still the First Time",
    ),
    # Appendix A7: "Tender and Strong" at the close of "On Marriage and
    # Submission" -- the song is the husband narrating his wife's tender,
    # stronger-than-his-own role in their covenant.
    (
        'appendix-a7.html',
        'Tit. 2:4-5',
        "still-the-first-time",
        "Tender and Strong",
        "Still the First Time",
    ),

    # ---- From Pride to Praise (6 placements) ----

    # Chapter 19 close (before Objections): "Humbled By Your Grace" --
    # doxological response to grace as gift.
    (
        'chapter-19.html',
        "And He\u2019s never missed",
        "from-pride-to-praise",
        "Humbled By Your Grace",
        "From Pride to Praise",
    ),
    # Chapter 18 close (before Objections): "In Shadows of Duality" -- the
    # two-natures-locked-in-strife song. Mirrors continuous-vs-progressive
    # sanctification thesis.
    (
        'chapter-18.html',
        'less sinful. More aware.',
        "from-pride-to-praise",
        "In Shadows of Duality",
        "From Pride to Praise",
    ),
    # Chapter 25 "The System Predicts Its Own Rejection" close: "It Ain't
    # My Strength" -- "We cannot beat the truth into minds... only the
    # Spirit of the Lord can make the truth take its tolls."
    (
        'chapter-25.html',
        'Christian irrational, which is itself',
        "from-pride-to-praise",
        "It Ain't My Strength",
        "From Pride to Praise",
    ),
    # Chapter 27 close (before For Further Study): "I Don't Know" --
    # Deuteronomy 29:29 in chorus form. Humility coda after eschatology.
    (
        'chapter-27.html',
        'I already addressed the popularity argument',
        "from-pride-to-praise",
        "I Don't Know",
        "From Pride to Praise",
    ),
    # Appendix M "Sola Gratia" close: "Puffed-Up Man" -- portrait of the
    # man Sola Gratia is meant to dethrone.
    (
        'appendix-m.html',
        'Given. Before. Done.',
        "from-pride-to-praise",
        "Puffed-Up Man",
        "From Pride to Praise",
    ),
    # Chapter 30 "The Test" close: "Professor or Possessor?" -- "Not just
    # a mind that knows His name, but a heart set free by grace." Direct
    # mirror of ch30's "who are you resting in?" thesis.
    (
        'chapter-30.html',
        'and let it do its',
        "from-pride-to-praise",
        "Professor or Possessor?",
        "From Pride to Praise",
    ),
    # Chapter 30 "knowledge-Calvinist narrowing" beat: "Loving the Brethren"
    # right after the paragraph that names the move -- "the tribe I came
    # from had accidentally smuggled an Arminian into the house... And it
    # led me out of their company." The song renders that narrowing as the
    # slow shrinking of one word ("brethren"), and the chorus answers it
    # from Matthew 5:46 -- even publicans love who looks like them.
    (
        'chapter-30.html',
        'smuggled an Arminian into the house',
        "ditch-the-garbage",
        "Loving the Brethren",
        "Ditch the Garbage!",
    ),

    # ---- In the Little Things (5 placements) ----

    # Appendix A11 "On Forgiving Someone Who Will Not Apologize" close:
    # "When the Wounds Run Deep" -- the Joseph-and-Paul forgiveness song.
    (
        'appendix-a11.html',
        "Author\u2019s purpose was settled before the frame played.",
        "in-the-little-things",
        "When the Wounds Run Deep",
        "In the Little Things",
    ),
    # Appendix A11 "On Guilt After Sin" close: "A Broken Heart" -- pure
    # Psalm 51 contrition. "Only brokenness can build His kingdom."
    (
        'appendix-a11.html',
        'ye sons of Jacob are not',
        "in-the-little-things",
        "A Broken Heart",
        "In the Little Things",
    ),
    # Appendix A11 "On the Fear of Man" close: "All This Noise Online" --
    # the song catalogues the noise of online opinions; the section names
    # "their rendering of you" -- a rendering of a rendering. Moved here
    # from "On Being Hurt by the Church" to give Rise Above breathing room.
    (
        'appendix-a11.html',
        'rendering of a rendering.',
        "in-the-little-things",
        "All This Noise Online",
        "In the Little Things",
    ),
    # Chapter 23 close: "Church Ain't a Museum" -- closes the chapter's
    # body-not-institution argument with the song's "house for the wounded."
    (
        'chapter-23.html',
        'neither one requires a building',
        "in-the-little-things",
        "Church Ain't a Museum",
        "In the Little Things",
    ),
    # Appendix A11 "On Loneliness" close: "When Every Friend Fades" -- Paul
    # crying "Timothy, come quickly," wife as anchor, Christ as ultimate Friend.
    (
        'appendix-a11.html',
        'process you at full',
        "in-the-little-things",
        "When Every Friend Fades",
        "In the Little Things",
    ),
    # Chapter 10 Communion section close: "Bread and Wine" -- song knocks down
    # transubstantiation and bare memorialism, widens into the floor swap.
    (
        'chapter-10.html',
        'Pour real wine.',
        "still-the-first-time",
        "Bread and Wine",
        "Still the First Time",
    ),
    # Appendix N Costume 15 (Bare Memorial) close: "Bread and Wine" again --
    # forward-pointing rendering, the now-table as foretaste of the then-table.
    (
        'appendix-n.html',
        'renders the then-table',
        "still-the-first-time",
        "Bread and Wine",
        "Still the First Time",
    ),
    # Chapter 11 "Adam Created Sinful" close: "Written" -- each soul directly
    # authored, no federal headship, no middleman. Addressed to the listener.
    (
        'chapter-11.html',
        'deliberately, purposefully',
        "still-the-first-time",
        "Written",
        "Still the First Time",
    ),
    # Chapter 11 "Federal Headship Rejected" opening: "Adam Didn't Sign My Name"
    # right after the punchline rejection. The song IS the federal-headship
    # rejection in audio form -- paradox-list confessional, no ledger transfer,
    # directly-authored sin nature, Orthodox convergence in the bridge.
    (
        'chapter-11.html',
        'And I reject it.',
        "ditch-the-garbage",
        "Adam Didn\u2019t Sign My Name",
        "Ditch the Garbage!",
    ),
    # Chapter 10 opening: "Before It Shows" -- the song's whole theme IS
    # invisible-precedes-visible / covenant-before-ceremony. Goes right after
    # the master-pattern setup paragraph.
    (
        'chapter-10.html',
        'system upside down.',
        "still-the-first-time",
        "Before It Shows",
        "Still the First Time",
    ),
    # Chapter 22 baptism: "Before It Shows" -- the Spirit is the sign, water is
    # the rendering. Same operational-idealism point applied to baptism.
    (
        'chapter-22.html',
        'The sign of the New Covenant is the Holy Spirit',
        "still-the-first-time",
        "Before It Shows",
        "Still the First Time",
    ),
    # Chapter 10 One-Flesh Union: "One Flesh" -- husband/wife duet on marital
    # intimacy as covenant-rendering, Christ and the church at lower resolution.
    (
        'chapter-10.html',
        'covenant rendered in intimacy',
        "still-the-first-time",
        "One Flesh",
        "Still the First Time",
    ),
    # Appendix A6 marital-sexuality section: the song's explicit target
    # per its purpose note. Goes in the Song-of-Solomon celebration passage.
    (
        'appendix-a6.html',
        'catechized by Plato',
        "still-the-first-time",
        "One Flesh",
        "Still the First Time",
    ),
    # Appendix N Costume 8 (Denigration of the Marriage Bed): "One Flesh"
    # renders the correction -- bed as sacrament without a priest.
    (
        'appendix-n.html',
        'Sacrament without a priest',
        "still-the-first-time",
        "One Flesh",
        "Still the First Time",
    ),
    # Chapter 28 "Heaven and Hell": "When the Glass Falls" after the paragraph
    # on the elect's experience of the glass coming down as glory. The song
    # IS that moment, sung from the curator's side at the seam.
    (
        'chapter-28.html',
        'Full circle.',
        "sweet-release",
        "When the Glass Falls",
        "Sweet Release",
    ),
    # Chapter 1 master-pattern opener: "Before It Shows" after the sentence
    # stating the book's governing axiom.
    (
        'chapter-01.html',
        'Always. In every',
        "still-the-first-time",
        "Before It Shows",
        "Still the First Time",
    ),
    # Chapter 2 "The Collapsed Thought": "Written" lands much later in the
    # chapter, in the "What This Means for Your Life" section right after
    # "You are an eternal thought" -- the song's exact thesis. Moved here
    # from the early filmstrip section to give Every Frame breathing room.
    (
        'chapter-02.html',
        'You are an eternal thought.',
        "still-the-first-time",
        "Written",
        "Still the First Time",
    ),
    # Appendix A6 Eschatology: "When the Glass Falls" after the master
    # heaven/hell paragraph -- one presence, two firmwares, the glass coming
    # down for everyone.
    (
        'appendix-a6.html',
        'shame at eternal intensity.',
        "sweet-release",
        "When the Glass Falls",
        "Sweet Release",
    ),
    # About page: "What Plato Built" after the paragraph that names the
    # paradigm shift since Augustine -- the book's whole project is replacing
    # the Platonic foundation Augustine imported. The song is that thesis
    # in audio form. Closes on "And I believe it holds."
    (
        'about.html',
        'And I believe it holds.',
        "still-the-first-time",
        "What Plato Built",
        "Still the First Time",
    ),
    # Preface: "Three Elders and a Door" at the close of the "three elders in
    # the office" rejection paragraph -- "that independence is what eventually
    # produced this book." The song narrates that exact morning: the summons,
    # the office, the three elders and the pulled-up empty chair, the tithing
    # charge, the stripping of his ministry, the drive home in tears.
    (
        'preface.html',
        'that independence is what eventually produced this book.',
        "outside-the-camp",
        "Three Elders and a Door",
        "Outside the Camp",
    ),
    # Appendix A10 (On Gatekeeping): "NOT ONE" at the close of the section,
    # right after the temple-cleansing paragraph that pairs the fury aimed
    # at gatekeepers with tenderness aimed at the people they excluded.
    # The song is the gospelist version of that diagnosis: the omniscient
    # verdict from the keyboard, the gate closing in the comments.
    (
        'appendix-a10.html',
        'gatekeepers\nexcluded.',
        "still-the-first-time",
        "NOT ONE",
        "Still the First Time",
    ),
    # Appendix A5 (On Deriving Instead of Defending): "NOT ONE" at the close
    # of the section -- "the theology is already dead." The defending posture
    # IS the gatekeeper posture; NOT ONE is what defending sounds like when
    # it goes public.
    (
        'appendix-a5.html',
        'theology is already dead.',
        "still-the-first-time",
        "NOT ONE",
        "Still the First Time",
    ),
    # Appendix N (Costume 2: Phariseeism): "Pharisees in Every Church" at the
    # close of the Framework correction -- "no longer a realm where the form
    # can be valued above the person." The song IS that diagnosis with the
    # discipline: see the Pharisees, do not run the hunt.
    (
        'appendix-n.html',
        'valued above the person.',
        "ditch-the-garbage",
        "Pharisees in Every Church",
        "Ditch the Garbage!",
    ),
    # Appendix A10 (On Heresy Hunting close): "Pharisees in Every Church" at
    # "Your job is meekness. His job is root access." The song's entire
    # discipline is the Author sorts the room, not me. Lands here as the
    # disciplinary close to the heresy-hunting diagnosis. (Pandoc wraps
    # mid-phrase so the marker uses a short unique fragment.)
    (
        'appendix-a10.html',
        'Your job is meekness.',
        "ditch-the-garbage",
        "Pharisees in Every Church",
        "Ditch the Garbage!",
    ),
    # Appendix N (Costume 10: Free-Willer Accusation as Tribal Test): "Names
    # They Call Me" at the close. The costume catalogs labels-as-tribal-test;
    # the song is the survival anthem AFTER the labels have landed -- every
    # label maps to a name they called Christ first.
    (
        'appendix-n.html',
        'five centuries policing.',
        "ditch-the-garbage",
        "Names They Call Me",
        "Ditch the Garbage!",
    ),
    # Prologue: "Names They Call Me" after "He wrote all of this without ever
    # speaking to me." -- the labels-as-coordinates theme lands as the song
    # right where the prologue describes being received before being heard.
    (
        'prologue.html',
        'speaking to me.',
        "ditch-the-garbage",
        "Names They Call Me",
        "Ditch the Garbage!",
    ),
    # Chapter 19 (The Gospel): "Head Over Feet for Me" after "Not generated
    # by a decision in the back pew during an altar call." The song is that
    # critique rendered tender -- not attacking the altar call but marveling
    # at the Author who authored every step before there was a step to take.
    (
        'chapter-19.html',
        'during an altar call.',
        "ditch-the-garbage",
        "Head Over Feet for Me",
        "Ditch the Garbage!",
    ),
    # Appendix I "The Augustinian Foundation" close: "Plato in a Suit" at
    # "inherited both without reexamination." The song IS the indictment of
    # exactly this inheritance -- Plato's Republic ethic + Plotinus's realist
    # hierarchy smuggled into Christian theology through Augustine.
    (
        'appendix-i.html',
        'inherited both without reexamination.',
        "ditch-the-garbage",
        "Plato in a Suit",
        "Ditch the Garbage!",
    ),
    # Appendix N Costume 4 (The Small Heaven): "Plato in a Suit" at the
    # Framework correction close. Verse 2's "heaven full of clouds /
    # release her spirit / cage was the problem" is the exact Small Heaven
    # diagnosis the song refuses with bodily resurrection. Marker uses a
    # short fragment before pandoc's wrap.
    (
        'appendix-n.html',
        'Christ is at the head of the table',
        "ditch-the-garbage",
        "Plato in a Suit",
        "Ditch the Garbage!",
    ),
    # Chapter 1: "The Room I Was Already In" at the close of the operational
    # idealism paragraph -- "in operational idealism, there is no gap between
    # the two." The song is the first-person experience of that ontology
    # finally landing. (Marker is the pre-wrap fragment; pandoc breaks the
    # sentence between "the" and "two" so a longer marker fails silently.)
    (
        'chapter-01.html',
        'operational idealism, there is no gap',
        "still-the-first-time",
        "The Room I Was Already In",
        "Still the First Time",
    ),
    # Appendix J: "The Room I Was Already In" at the climax of the Acts 17:28
    # / IN-Him argument. The song is that climax in audio form.
    (
        'appendix-j.html',
        'The gap is gone.',
        "still-the-first-time",
        "The Room I Was Already In",
        "Still the First Time",
    ),
    # Appendix A10 (The Render Walked In): "The Room I Was Already In" inside
    # the closing paragraph that says "The Author is in every room." -- the
    # exact echo of the song title. The section IS the song in prose.
    (
        'appendix-a10.html',
        'The Author is in every room.',
        "still-the-first-time",
        "The Room I Was Already In",
        "Still the First Time",
    ),
    # Appendix A3 (Justification From Eternity): "Am I Really?" right after
    # the paragraph that distinguishes Spirit-firmware witness from application-
    # layer self-examination. The song IS the dissolving of the examine-yourself
    # spiral that the paragraph names. Reframes the question from "Am I really
    # His?" to "Is He really mine?"
    (
        'appendix-a3.html',
        'Not self-examination producing confidence.',
        "ditch-the-garbage",
        "Am I Really?",
        "Ditch the Garbage!",
    ),
    # Appendix N (Costume 3 - Gospelism): "Wolves, Wolves, Wolves" right after
    # the "Christian appearance" paragraph that names "defending the gospel
    # against compromisers, naming the wolves, standing for the truth at any
    # cost." The song IS the costume in audio form -- the wolf-naming industry
    # diagnosed and inverted: Christ drove the watchmen out of the temple, not
    # the publicans and harlots.
    (
        'appendix-n.html',
        'Naming the wolves.',
        "ditch-the-garbage",
        "Wolves, Wolves, Wolves",
        "Ditch the Garbage!",
    ),
    # Appendix A8 (On Tithing and Giving): "Storehouse Math" right after the
    # paragraph that names "the church that demands a tithe has reimposed the
    # law that Christ fulfilled." The song IS the tithing-sermon takedown in
    # audio form, with the same 2 Corinthians 9:7 verse anchoring its bridge.
    (
        'appendix-a8.html',
        'The church that demands a tithe has reimposed the',
        "ditch-the-garbage",
        "Storehouse Math",
        "Ditch the Garbage!",
    ),
    # Chapter 27 "Why Not Premillennialism?": "The Chart on the Wall" at the
    # close of the prophecy-charts/timelines/date-calculations paragraph --
    # "more false predictions and more embarrassed prophets than any other
    # system in the history of the church." The song's V2 catalogs the exact
    # failed dates ('88, '93, Y2K, blood moons, the Jubilee calculations) and
    # ends with the chart falling off the wall when the cross takes its place.
    (
        'chapter-27.html',
        'newspaper exegesis',
        "ditch-the-garbage",
        "The Chart on the Wall",
        "Ditch the Garbage!",
    ),
    # Appendix A6 "On the Rapture": "The Chart on the Wall" at the close of
    # the section that refuses the two-stage return -- "one Christ, one coming,
    # one trumpet, one rendering upgrade." The song's bridge is the same
    # thesis: "Not seven dispensations stacked like floors / Not the seventy
    # weeks split across two millennia / Not the church a parenthesis in a
    # bigger plan / One history / One Author / One cross at the middle."
    (
        'appendix-a6.html',
        'one trumpet, one rendering upgrade',
        "ditch-the-garbage",
        "The Chart on the Wall",
        "Ditch the Garbage!",
    ),

    # ---- Sing Anyway (8th album, 2026) -- 12 chips. Three songs of the
    # album have no single-passage home and stay chip-less: the opener
    # "Come In From the Cold", the praise-command "Raise the Song", and the
    # title track "Sing Anyway". Placements kept within the book's 9-chip-
    # per-chapter ceiling.

    # Ch 11 (Every Person Authored): "Holy, and He Knows My Name" -- the song
    # is authored-by-name; lands on the Potter-and-vessel paragraph.
    (
        'chapter-11.html',
        'Potter who makes each vessel from the lump',
        'sing-anyway',
        'Holy, and He Knows My Name',
        'Sing Anyway',
    ),
    # Ch 15 (Justification): "Nothing Left to Pay" -- the finished cross,
    # nothing remains to pay, after the "it is finished" argument.
    (
        'chapter-15.html',
        'contingent on anything after Calvary',
        'sing-anyway',
        'Nothing Left to Pay',
        'Sing Anyway',
    ),
    # Ch 15 (Justification): "Counted Righteous" -- God never viewed His
    # elect as condemned; lands on that section's opening declaration.
    (
        'chapter-15.html',
        'That thought does not exist.',
        'sing-anyway',
        'Counted Righteous',
        'Sing Anyway',
    ),
    # Appendix A3 (Salvation Applied): "He Did It All" -- the golden chain,
    # grace doing every link; lands on the "whole ordo" paragraph.
    (
        'appendix-a3.html',
        'Grace precedes. Grace prepares. Grace arrives.',
        'sing-anyway',
        'He Did It All',
        'Sing Anyway',
    ),
    # Ch 16 (The Firmware): "You Called Me Out of the Dark" -- the effectual
    # call, the Spirit rewriting the dead soul.
    (
        'chapter-16.html',
        'change the boot parameters',
        'sing-anyway',
        'You Called Me Out of the Dark',
        'Sing Anyway',
    ),
    # Appendix A11 (The Bedside): "Even Here" -- praise from inside the
    # wound; lands on the silence-was-a-frame, mercy-was-the-filmstrip line.
    (
        'appendix-a11.html',
        'The silence was a frame. The mercy was the filmstrip',
        'sing-anyway',
        'Even Here',
        'Sing Anyway',
    ),
    # Ch 29 (The Higher Resolution Rendering): "We Sing Through Tears" --
    # grief held with hope; lands on Mary weeping at the empty tomb.
    (
        'chapter-29.html',
        'She thought He was the gardener.',
        'sing-anyway',
        'We Sing Through Tears',
        'Sing Anyway',
    ),
    # Preface (Campless): "From the Cold Field" -- the lone campless man;
    # lands on the "I am theologically homeless" declaration.
    (
        'preface.html',
        'I am theologically homeless',
        'sing-anyway',
        'From the Cold Field',
        'Sing Anyway',
    ),
    # Ch 23 (The Church): "A Camp With No Walls" -- the church is people,
    # not a building.
    (
        'chapter-23.html',
        'a pastor, a board, and a tax exemption',
        'sing-anyway',
        'A Camp With No Walls',
        'Sing Anyway',
    ),
    # Appendix L (A Vision of the Final State): "The Country Ahead" -- the
    # pilgrim, eyes on home; lands on "the weeping of a man finally home."
    (
        'appendix-l.html',
        'The weeping of a man finally home',
        'sing-anyway',
        'The Country Ahead',
        'Sing Anyway',
    ),
    # Ch 28 (Heaven and Hell): "Then Face to Face" -- the glass, fully
    # known; lands on the 1 Corinthians 13:12 quotation.
    (
        'chapter-28.html',
        'through a glass, darkly; but then face to face',
        'sing-anyway',
        'Then Face to Face',
        'Sing Anyway',
    ),
    # Epilogue: "Grace and Peace" -- the catalog's closing benediction;
    # lands on the closing peace paragraph, just before the sign-off.
    (
        'epilogue.html',
        'I would not trade it for anything in the world',
        'sing-anyway',
        'Grace and Peace',
        'Sing Anyway',
    ),
    # Made of Light (album 11, complete 2026-06-12) -- the cosmology album:
    # chapters 1-4 / 9 / 11 / 16 / 29 + appendices A1, G, H, J per the album roadmap.
    (
        'appendix-a1.html',
        'described by physicists who will\nnot say the word God',
        "made-of-light",
        "Made of Light",
        "Made of Light",
    ),
    (
        'chapter-02.html',
        'open theism is\njust deism with',
        "made-of-light",
        "Hum of the Render",
        "Made of Light",
    ),
    (
        'chapter-03.html',
        'The visible cosmos',
        "made-of-light",
        "Spoken",
        "Made of Light",
    ),
    (
        'chapter-04.html',
        'If God is outside of time',
        "made-of-light",
        "The Long Light Year",
        "Made of Light",
    ),
    (
        'chapter-09.html',
        'rendered into human\nexperience at increasing resolution',
        "made-of-light",
        "Pixels of Eden",
        "Made of Light",
    ),
    (
        'chapter-11.html',
        'Two\nseeds, each created directly from the womb',
        "made-of-light",
        "A Billion Little Suns",
        "Made of Light",
    ),
    (
        'appendix-a1.html',
        'The rocks and the stars and the animals',
        "made-of-light",
        "Counting Hairs and Galaxies",
        "Made of Light",
    ),
    (
        'appendix-j.html',
        'Edwards was standing in the same field.',
        "made-of-light",
        "Dream in His Head",
        "Made of Light",
    ),
    (
        'appendix-g.html',
        'proposes a\nmachine, not a mind',
        "made-of-light",
        "Static and Stars",
        "Made of Light",
    ),
    (
        'appendix-h.html',
        'The observer effect confirms it',
        "made-of-light",
        "Particle and Wave",
        "Made of Light",
    ),
    (
        'chapter-16.html',
        'waking up to what the Spirit\nalready did',
        "made-of-light",
        "The Lights Came On",
        "Made of Light",
    ),
    (
        'chapter-29.html',
        'about the\nhigher resolution rendering',
        "made-of-light",
        "Brighter Than I Dreamed",
        "Made of Light",
    ),
]


def _attr(s):
    """Escape a string for use inside a double-quoted HTML attribute."""
    return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')


def build_chip(source_album, song_title, album_title):
    # The chip identifies the song by (sourceAlbum, title) and resolves its
    # current All Music position at click time -- so inserting songs into the
    # arc never invalidates a chip. The title travels in a data- attribute and
    # the onclick reads it from this.dataset, so apostrophes need no escaping.
    #
    # Behavior (2026-05-23): clicking a chip ADDS the song to Up Next and
    # opens the Up Next popup with the new row pulsing green. It no longer
    # starts playback immediately -- the reader chooses to start it by
    # clicking the row in the popup. The chip simplified to one button with
    # one icon (album subline + separate + button both dropped).
    safe_title = _attr(song_title)
    safe_src = _attr(source_album)
    data_attrs = f'data-source-album="{safe_src}" data-song-title="{safe_title}"'
    # One <div> with exactly one </div> -- the chip-strip regex in inject()
    # is non-greedy and would mis-match a nested div.
    return (
        '<div class="chapter-song-chip">'
        '<button type="button" class="chapter-song-chip-play" '
        f'{data_attrs} '
        'onclick="if(window.bookMusicQueueChip){window.bookMusicQueueChip(this.dataset.sourceAlbum,this.dataset.songTitle,this);}" '
        'title="Add to Up Next" aria-label="Add to Up Next">'
        '<span class="chapter-song-chip-icon"><i class="bi bi-play-circle-fill"></i></span>'
        '<span class="chapter-song-chip-text">'
        f'<span class="chapter-song-chip-title">{safe_title}</span>'
        '</span>'
        '</button>'
        '</div>'
    )


def inject(chapters_dir):
    # First pass: strip every existing chapter-song-chip div from every chapter
    # file. Static front-matter pages (about/title-page/cover/copyright/dedication)
    # are NOT regenerated by pandoc, so chips would otherwise accumulate across
    # builds. Stripping first makes the whole script idempotent: every build
    # ends with exactly the chips listed in SONGS, nothing more.
    chip_pattern = re.compile(r'\n?<div class="chapter-song-chip">.*?</div>\s*', re.DOTALL)
    for html_name in os.listdir(chapters_dir):
        if not html_name.endswith('.html'):
            continue
        html_path = os.path.join(chapters_dir, html_name)
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        new_html = chip_pattern.sub('\n', html)
        if new_html != html:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(new_html)

    count = 0
    for entry in SONGS:
        filename, marker, source_album, song_title, album_title = entry[:5]
        close_tag = entry[5] if len(entry) > 5 else '</p>'
        path = os.path.join(chapters_dir, filename)
        if not os.path.isfile(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        if marker not in html:
            print(f"  marker not found in {filename}: {marker!r}", file=sys.stderr)
            continue
        chip = build_chip(source_album, song_title, album_title)
        # Find the close_tag after the marker; insert chip right after it
        idx = html.find(marker)
        close_at = html.find(close_tag, idx)
        if close_at == -1:
            print(f"  couldn't find {close_tag!r} after marker in {filename}", file=sys.stderr)
            continue
        insert_at = close_at + len(close_tag)
        # Skip if this exact chip is already immediately after this insertion point
        # (allows the same song to appear in multiple locations within one chapter).
        if html[insert_at:insert_at + len(chip) + 32].lstrip().startswith(chip):
            continue
        new_html = html[:insert_at] + '\n' + chip + html[insert_at:]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_html)
        count += 1
    print(f" done ({count} song chip{'s' if count != 1 else ''} injected)")


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    inject(chapters_dir)
