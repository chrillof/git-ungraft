git ungraft is a tool for ungrafting commits when working with shallow clones
of repositories. It investigates the grafted commits to check whether or not
their parents are present locally and removes the graft tag, effectively 
restoring the history between the commits.

When shallowly fetching commits with e.g. `depth=1` they will all have the graft
tag, even if the commits are directly related as parent/child commits. This tool
is used to remove the graft tag on those commits which have all their parents
locally present.
