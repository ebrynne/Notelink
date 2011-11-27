Notelink
========
Notelink seeks to offer simple, clean text editing with powerful organization tools. 

Notelink started as a weekend project but quickly bled into the rest of the week. Although it never got really polished, it's one of my favourite little projects, and also marks my first attempt at a non-html gui. 

Notelink is a simple text editor with limited formatting capabilites, written in python and using py-gtk. It is built around two key features, the first of which is the ability to embed Notes inline in other notes, where they can be compressed, expanded, editted, and clicked on to open the embedded note itself. Referencing other work and content is easy this way, allowing users to connect disperate ideas without having to modify the overlying organization to accomidate them both in some fashion. 

The second feature which defines notelink is the tagging/grouping functionality. Each note can be tagged with user created labels, which are searchable and prsent a convenient list of the content notes that have that tag applied. Users can also create views, which are collection of tags and other views, some of which are organized in to groups. The groups each represent the set of notes comprised by the intersection of all their elements, and the iews represent the union of all sets of notes represented by any of their groups and ungrouped elements. As confusing as this is to explain, it makes it very easy to create a view that for important school work by grouping 'Important' and 'Schoolwork', or a conglomerate view of several different projects by adding each with any modifying tags needed.

For a demo, there's a video I made in early stages of the project available here: http://vimeo.com/21148413 
