# Online bin packing

Items arrive one at a time. Each must be placed the moment it arrives, into an
open bin that fits it or into a new one, and it is never moved again. Use as
few bins as possible.

`priority(item, bins)` is the whole decision. `bins` holds the remaining
capacity of every open bin the item fits in, and you return one score per bin;
the item goes to the highest scorer. An empty list never reaches you -- when
nothing fits, a new bin opens without asking.

The seed is best fit: prefer the tightest bin. It is the standard baseline and
it is beatable. The known weakness is that it is greedy about the item in
front of it and blind to the sequence: it will fill a bin down to three units
of slack, and those three units are then almost certainly wasted for good.

Things that are true and worth using:

- Item sizes are integers between 20 and 100. Bin capacity is 150. So a bin
  with less than 20 left can never take another item.
- At most three items of size >50 fit in a bin, and often only two.
- You know the capacity implicitly: no bin can have more than 150 remaining.

Constraints:

- Return exactly one number per bin, and no NaN.
- No randomness. The same input must give the same output every time; the
  scorer runs the training set twice and rejects a candidate whose two scores
  differ.
- Standard library only, and no I/O. You are scored on instances you cannot
  see.
