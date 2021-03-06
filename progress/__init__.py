# Copyright (c) 2012 Giorgos Verigakis <verigak@gmail.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from __future__ import division

from collections import deque
from datetime import timedelta
from math import ceil
from sys import stderr
from time import time


__version__ = '1.2'


"""
The moving average is calculated by this formula:

  _in_window / (time() - oldest_timestamp_in_window)

Because the frequency of calling next() callback might be rather very high,
doing the naive next()/avg() implementation leads to issues (PR 23):

  def next(N):
     t = time()
     delta = N / (t - last_timestamp) # very small number
     _dt.append(delta)
     _avg = sum(_dt)/len(_dt)
     last_timestamp = t

.. Even if 'len(_dt)' was 1000, the time frame can be very small (e.g. file
download for next(N=8k in bytes) on 1Gbit network.  With the mentioned formula
the window size is limited by *time*, not by the next() callback frequency.

The moving average is calculated -at most- for the last 3 seconds by default:

  sma_window x sma_delta = 10 x 0.3 = 3s

Users can change this default window size, when needed.
"""
class Infinite(object):
    file = stderr
    sma_window = 10     # Size of the window -- (max) number of sma_delta items.
    sma_delta  = 0.3    # Time-length of one item in window, in seconds.

    def __init__(self, *args, **kwargs):
        self.index = 0
        self.start_ts = time()
        self._ts = self.start_ts
        self._dt = deque()
        self._in_window = 0
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __getitem__(self, key):
        if key.startswith('_'):
            return None
        return getattr(self, key, None)

    @property
    def avg(self):
        if not self._in_window:
            return 0
        return (self._ts - self._dt[0]['t']) / self._in_window

    @property
    def elapsed(self):
        return int(time() - self.start_ts)

    @property
    def elapsed_td(self):
        return timedelta(seconds=self.elapsed)

    def update(self):
        pass

    def start(self):
        pass

    def finish(self):
        pass

    def next(self, n=1):
        self._ts = time()

        item = {'t': self._ts, 'n': 0}
        if len(self._dt):
            old_item = self._dt.pop()
            if self._ts > old_item['t'] + self.sma_delta:
                # Already reached timeout, we are not going to
                # touch this item.  Return it back.
                self._dt.append(old_item)
            else:
                item = old_item

        item['n'] = item['n'] + n

        self._dt.append(item)
        self._in_window = self._in_window + n

        if len(self._dt) > self.sma_window:
            item = self._dt.popleft()
            self._in_window = self._in_window - item['n']

        self.index = self.index + n
        self.update()

    def iter(self, it):
        try:
            for x in it:
                yield x
                self.next()
        finally:
            self.finish()


class Progress(Infinite):
    def __init__(self, *args, **kwargs):
        super(Progress, self).__init__(*args, **kwargs)
        self.max = kwargs.get('max', 100)

    @property
    def eta(self):
        return int(ceil(self.avg * self.remaining))

    @property
    def eta_td(self):
        return timedelta(seconds=self.eta)

    @property
    def percent(self):
        return self.progress * 100

    @property
    def progress(self):
        return min(1, self.index / self.max)

    @property
    def remaining(self):
        return max(self.max - self.index, 0)

    def start(self):
        self.update()

    def goto(self, index):
        incr = index - self.index
        self.next(incr)

    def iter(self, it):
        try:
            self.max = len(it)
        except TypeError:
            pass

        try:
            for x in it:
                yield x
                self.next()
        finally:
            self.finish()
