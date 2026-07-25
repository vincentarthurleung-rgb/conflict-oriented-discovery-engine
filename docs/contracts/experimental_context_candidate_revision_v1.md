# Experimental Context Candidate Revision v1

A candidate revision losslessly wraps one historical or future Context payload.
It is immutable, may supersede but never overwrite another revision, and is not
a validated Context. The payload hash, extractor and schema versions, precise
source artifact references, warnings, and lineage limitations are required.

Conflict comparison and adjudication fields are forbidden recursively.

