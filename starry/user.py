"""User-facing routines for STARRY."""
import numpy as np
from .rotation import R, Rz
from .basis import A, evaluate_poly, y2p
from .integrals import S, brute
from .maps import image2map, healpix2map
from .utils import prange
import matplotlib.pyplot as pl
from matplotlib.animation import FuncAnimation


__all__ = ["starry"]


class starry(np.ndarray):
    """The main STARRY interface. This is a subclass of numpy.ndarray."""

    def __new__(subtype, lmax, image=None, tol=1e-15, u1=None, u2=None):
        """Create a new `starry` instance by subclassing ndarray."""
        # Check that lmax is a nonnegative integer
        assert type(lmax) is int, "Argument `lmax` must be an integer."
        assert lmax >= 0, "Argument `lmax` must be >= 0."

        # Instantiate a numpy array
        shape = (lmax + 1) ** 2
        obj = super(starry, subtype).__new__(subtype, shape, float,
                                             None, 0, None,
                                             None)

        # Initialize with zeros
        obj[:] = 0
        obj.lmax = lmax
        obj.tol = tol

        # Pre-compute the basis change matrix
        obj.A = A(obj.lmax)

        # Did the user set the limb darkening coefficients?
        if (u1 is not None) or (u2 is not None):
            # Check that lmax is correct
            assert lmax == 2, "Parameter lmax must be 2 " + \
                              "for quadratic limb darkening."
            assert image is None, "Cannot set both limb darkening " + \
                                  "parameters and a map image."
            if u1 is None:
                u1 = 0
            elif u2 is None:
                u2 = 0
            obj[0] = 2 * np.sqrt(np.pi) / 3. * (3 - 3 * u1 - 4 * u2)
            obj[2] = 2 * np.sqrt(np.pi / 3.) * (u1 + 2 * u2)
            obj[6] = -4. / 3. * np.sqrt(np.pi / 5) * u2

        # Did the user specify an image map?
        if image is not None:
            # Is this a string?
            if type(image) is str:
                obj[:] = image2map(image, lmax=lmax)
            # Or is this a healpix array?
            elif type(image) is np.ndarray:
                obj[:] = healpix2map(image, lmax=lmax)
            else:
                raise ValueError("Invalid `image` value.")
        return obj

    @property
    def y(self):
        """Return an ndarray copy of the ylm vector."""
        return self.__array__()

    def __array_finalize__(self, obj):
        """Finalize the array (needed for ndarray subclasses)."""
        if obj is None:
            return
        self.info = getattr(obj, 'info', None)

    def __str__(self):
        """Return a string representation of the map."""
        terms = []
        n = 0
        for l in range(self.lmax + 1):
            for m in range(-l, l + 1):
                if np.abs(self[n]) > self.tol:
                    if self[n] == 1:
                        terms.append("Y_{%d,%d}" % (l, m))
                    elif self[n] == -1:
                        terms.append("-Y_{%d,%d}" % (l, m))
                    elif self[n] == int(self[n]):
                        terms.append("%d Y_{%d,%d}" % (self[n], l, m))
                    else:
                        terms.append("%.2e Y_{%d,%d}" % (self[n], l, m))
                n += 1
        if len(terms) == 0:
            return "%.2e" % 0
        res = " + ".join(terms)
        res = res.replace("+ -", "- ")
        return res

    def __getitem__(self, lm):
        """Allow users to access elements using their `l` and `m` indices."""
        try:
            l, m = lm
            n = l ** 2 + l + m
            if (l < 0) or (n >= len(self.y)) or (np.abs(m) > l):
                raise ValueError("Invalid value for `l` and/or `m`.")
        except (TypeError, ValueError):
            n = lm
        return super(starry, self).__getitem__(n)

    def __setitem__(self, lm, val):
        """Allow users to set elements using their `l` and `m` indices."""
        try:
            l, m = lm
            n = l ** 2 + l + m
            if (l < 0) or (n >= len(self.y)) or (np.abs(m) > l):
                raise ValueError("Invalid value for `l` and/or `m`.")
        except (TypeError, ValueError):
            n = lm
        return super(starry, self).__setitem__(n, val)

    def __add__(self, y):
        """Implement addition for two `starry` objects of different sizes."""
        assert type(y) is starry, "Only `starry` instances can be added."
        if len(self) == len(y):
            z = self + y
            z.lmax = self.lmax
        elif len(self) > len(y):
            z = self.copy()
            z[:len(y)] += y
            z.lmax = self.lmax
        else:
            z = y.copy()
            z[:len(self)] += self
            z.lmax = y.lmax
        return z

    def flux(self, u=[0, 1, 0], theta=0, x0=None, y0=None, r=None, debug=False,
             res=100, quiet=False):
        """Return the flux visible from the map."""
        # Is this an occultation?
        if (x0 is None) or (y0 is None) or (r is None):
            # Vectorize the phase
            occultation = False
            theta = np.atleast_1d(theta)
            npts = len(theta)
            static_map = False
        else:
            # Vectorize the inputs
            occultation = True
            x0 = np.atleast_1d(x0)
            y0 = np.atleast_1d(y0)
            r = np.atleast_1d(r)
            theta = np.atleast_1d(theta)
            npts = max(len(x0), len(y0), len(r), len(theta))
            if len(x0) == 1:
                x0 = np.ones(npts, dtype=float) * x0[0]
            if len(y0) == 1:
                y0 = np.ones(npts, dtype=float) * y0[0]
            if len(r) == 1:
                r = np.ones(npts, dtype=float) * r[0]
            if len(theta) == 1:
                static_map = True
                theta = np.ones(npts, dtype=float) * theta[0]
            else:
                static_map = False
            assert len(x0) == len(y0) == len(r) == len(theta), \
                "Invalid dimensions for `x0`, `y0`, `r`, and/or `theta`."

        # Is the map static during the occultation?
        # If so, pre-compute the phase rotation matrix
        if static_map:
            R1 = R(self.lmax, u, np.cos(theta[0]),
                   np.sin(theta[0]), tol=self.tol)
            Ry = np.dot(R1, self.y)

        # Is there no occultation at all?
        # If so, pre-compute the integrals
        if not occultation:
            sT = S(self.lmax, np.inf, 1)

        # Iterate through the timeseries
        F = np.zeros(npts, dtype=float)
        for n in prange(npts, quiet=(quiet or npts == 1)):

            # Compute the impact parameter
            if occultation:
                b = np.sqrt(x0[n] ** 2 + y0[n] ** 2)
            else:
                b = np.inf

            # Rotate the map so the occultor is along the y axis
            if (occultation) and (b > self.tol) \
                    and (not debug) and (b < 1 + r[n]):
                sinvt = x0[n] / b
                cosvt = y0[n] / b
                R2 = Rz(self.lmax, cosvt, sinvt, tol=self.tol)
            # If there's no occultation, if b is zero, or if we
            # are computing the flux numerically,
            # we don't need to rotate
            else:
                R2 = np.eye((self.lmax + 1) ** 2)

            # If the map is static, we need only rotate about z
            if static_map:
                RRy = np.dot(R2, Ry)
            # For a rotating map, we need to apply two rotations
            else:
                R1 = R(self.lmax, u, np.cos(theta[n]),
                       np.sin(theta[n]), tol=self.tol)
                Ry = np.dot(R1, self.y)
                RRy = np.dot(R2, Ry)

            # Are we computing the flux numerically...
            if debug:
                if occultation:
                    F[n] = brute(RRy, x0[n], y0[n], r[n], res=res)
                else:
                    F[n] = brute(RRy, 99, 99, 1, res=res)
            # ...or analytically?
            else:
                # Convert to the Greens basis
                ARRy = np.dot(self.A, RRy)
                # Compute the integrals and solve for the flux array
                if occultation:
                    sT = S(self.lmax, b, r[n])
                F[n] = np.dot(sT, ARRy)

        return F

    def rotate(self, u=[0, 1, 0], theta=0):
        """Rotate the base map."""
        self[:] = np.dot(R(self.lmax, u, np.cos(theta), np.sin(theta),
                           tol=self.tol), self.y)

    def render(self, u=[0, 1, 0], theta=0, x0=None, y0=None, r=None, res=100):
        """Return a pixelized image of the visible portion of the map."""
        # Is this an occultation?
        if (x0 is None) or (y0 is None) or (r is None):
            x0 = 0
            y0 = 0
            r = 0

        # Rotate the map
        y = np.dot(R(self.lmax, u, np.cos(theta), np.sin(theta), tol=self.tol),
                   self.y)

        # Convert it to a polynomial
        poly = y2p(y)

        # Render it
        F = np.zeros((res, res)) * np.nan
        for i, x in enumerate(np.linspace(-1, 1, res)):
            for j, y in enumerate(np.linspace(-1, 1, res)):
                # Are we inside the body?
                if (x ** 2 + y ** 2 < 1):
                    # Are we outside the occultor?
                    if (x - x0) ** 2 + (y - y0) ** 2 > r ** 2:
                        F[j][i] = evaluate_poly(poly, x, y)

        return F

    def show(self, cmap='plasma', **kwargs):
        """Show the rendered map using `imshow`."""
        F = self.render(**kwargs)
        fig, ax = pl.subplots(1, figsize=(3, 3))
        ax.imshow(F, origin="lower", interpolation="none", cmap=cmap)
        ax.axis('off')
        pl.show()

    def _step(self, j):
        """Take an animation step."""
        u = self._animation['u']
        res = self._animation['res']
        theta = self._animation['theta'][j]
        x0 = self._animation['x0'][j]
        y0 = self._animation['y0'][j]
        r = self._animation['r'][j]
        F = self.render(u=u, theta=theta, x0=x0, y0=y0, r=r, res=res)
        self._img.set_data(F)
        return self._img,

    def animate(self, u=[0, 1, 0],
                theta=np.linspace(0, 2 * np.pi, 30, endpoint=False),
                x0=None, y0=None, r=None, res=50,
                cmap='plasma', interval=50, gif=None,
                fps=10, dpi=100, vmin=None, vmax=None, **kwargs):
        """Show an animation of the rendered map."""
        # Vectorize the inputs
        if (x0 is None) or (y0 is None) or (r is None):
            x0 = -1
            y0 = -1
            r = 0
        x0 = np.atleast_1d(x0)
        y0 = np.atleast_1d(y0)
        r = np.atleast_1d(r)
        theta = np.atleast_1d(theta)
        npts = max(len(x0), len(y0), len(r), len(theta))
        if len(x0) == 1:
            x0 = np.ones(npts, dtype=float) * x0[0]
        if len(y0) == 1:
            y0 = np.ones(npts, dtype=float) * y0[0]
        if len(r) == 1:
            r = np.ones(npts, dtype=float) * r[0]
        if len(theta) == 1:
            theta = np.ones(npts, dtype=float) * theta[0]
        assert len(x0) == len(y0) == len(r) == len(theta), \
            "Invalid dimensions for `x0`, `y0`, `r`, and/or `theta`."
        self._animation = dict(u=u,
                               theta=theta,
                               x0=x0,
                               y0=y0,
                               r=r,
                               res=res)
        self._fig, self._ax = pl.subplots(1, figsize=(3, 3))
        self._ax.axis('off')
        F = self.render(u=u, theta=theta[0], x0=x0[0], y0=y0[0], r=r[0],
                        res=res)
        self._img = self._ax.imshow(F, origin="lower", interpolation="none",
                                    cmap=cmap, vmin=vmin, vmax=vmax)
        animation = FuncAnimation(self._fig, self._step,
                                  frames=npts,
                                  interval=interval,
                                  repeat=True, blit=True)
        if gif is None:
            pl.show()
        else:
            animation.save(gif, writer='imagemagick', fps=fps, dpi=dpi)
