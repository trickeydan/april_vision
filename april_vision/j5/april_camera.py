"""
SR custom behaviour for Zoloto.

- Overriding the camera so that only the markers we want are captured
- Map the development and competition markers into the correct ranges
- Determine the size of a marker given the ID
- Determine which OpenCV calibration to use for the currently connected camera.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Type, Union, Container

from numpy.typing import NDArray

from j5.backends import Backend
from j5.boards import Board
from j5.components.component import Component

from .._version import __version__
from ..marker import MarkerType, Marker
from ..vision import Camera
from ..detect_cameras import _find_cameras

LOGGER = logging.getLogger(__name__)

# TODO add filter hooks to do "markers in game" and marker offset


class AprilCameraBoard(Board):
    """
    Virtual Camera Board for detecting fiducial markers.
    Additionally, it will do pose estimation, along with some calibration
    in order to determine the spatial positon and orientation of the markers
    that it has detected.
    """

    name: str = "AprilTag Camera Board"

    def __init__(self, serial: str, backend: 'AprilTagHardwareBackend'):
        self._serial = serial
        self._backend = backend

    @property
    def serial_number(self) -> str:
        """Get the serial number."""
        return self._serial

    @property
    def firmware_version(self) -> Optional[str]:
        """Get the firmware version of the board."""
        return self._backend.firmware_version

    def make_safe(self) -> None:
        """
        Close the camera.
        The camera will no longer work after this method is called.
        """
        self._backend.close_camera(self._identifier)

    @staticmethod
    def supported_components() -> Set[Type[Component]]:
        """List the types of components supported by this board."""
        return set()

    # Proxy methods from MarkerCamera object
    def see(self, *, eager: bool = True) -> List[Marker]:
        """
        Capture an image and identify fiducial markers.
        :param eager: Process the pose estimations of markers immediately,
            currently unused.
        :returns: list of markers that the camera could see.
        """
        return self._backend.see(self._identifier)

    def see_ids(self) -> List[int]:
        """
        Capture an image and identify fiducial markers.
        This method returns just the marker IDs that are visible.
        :returns: A list of IDs for the markers that were visible.
        """
        return self._backend.see_ids(self._identifier)

    def capture(self) -> NDArray:
        """
        Get the raw image data from the camera.
        :returns: Camera pixel data
        """
        return self._backend.capture_frame()

    def save(self, path: Union[Path, str]) -> None:
        """Save an annotated image to a path."""
        self._backend.save_annotated_image(self._identifier, path)


class AprilTagHardwareBackend(Backend):
    """An April Vision Hardware backend."""

    board = AprilCameraBoard
    marker_type = MarkerType.APRILTAG_36H11

    @classmethod
    def discover(cls) -> Set[Board]:
        """Discover boards that this backend can control."""
        return {
            AprilCameraBoard(
                str(camera_data.index),
                cls(camera_data.index, calibration_file=camera_data.calibration),
            )
            for camera_data in _find_cameras()
        }

    def __init__(self, camera_id: int, calibration_file: Union[Path, str]) -> None:
        self._cam = Camera.from_calibration_file(
            camera_id,
            calibration_file=calibration_file,
        )

    def see(
        self,
        identifier: int,
    ) -> List[Marker]:
        """
        Get markers that the camera can see.
        :param identifier: Camera identifier, ignored.
        """
        return self._cam.see()

    def save_annotated_image(self, identifier: int, file: Path) -> None:
        """
        Save an annotated image to a file.
        :param identifier: Camera identifier, ignored.
        """
        self._cam.save(file)

    def see_ids(self, identifier: int) -> List[int]:
        """
        Get a list of visible marker IDs.
        :param identifier: Camera identifier, ignored.
        :returns: List of marker IDs that were visible.
        """
        return self._cam.see_ids()

    def capture_frame(self) -> NDArray:
        """
        Get the raw image data from the camera.
        :returns: Camera pixel data
        """
        return self._cam.capture()

    @property
    def firmware_version(self) -> Optional[str]:
        """The firmware version of the board."""
        return f"April camera v{__version__}"

    def close_camera(self, identifier: int) -> None:
        """Close the camera object."""
        self._cam.close()

    def set_marker_sizes(self, marker_sizes: Dict[Container[int], int]) -> None:
        """Set the sizes of all the markers used in the game."""
        # Reset previously stored sizes
        self._cam.tag_sizes = {}
        for marker_ids, marker_size in marker_sizes.items():
            # Unroll generators to give direct lookup
            for marker_id in marker_ids:
                # Convert to meters
                self._cam.tag_sizes[marker_id] = float(marker_size) / 1000
