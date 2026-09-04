# Open-source release boundary

The complete semifinal environment, frozen configurations, test suite, action logs,
synthetic noise schedules, aggregate results, figures, and report are released in
this public repository under the licences stated in `LICENSE` and
`DATA_LICENSE.md`.

No source file, dataset, model weight, API credential, or result is withheld from
the reproducible experiment. The release has no network call during simulation and
does not depend on a hosted service. Internet access is needed only to install the
locked open-source dependencies.

The following are outside the release because they do not exist in this study:
hardware calibration records, proprietary optical-device specifications, private
scientific data, commercial API traces, closed-source model outputs, and expert
validation. If any such material is introduced in future work, it must be disclosed
and released only with the data or device owner's permission.

The immutable preliminary snapshot is tagged `round1-v1.0.0`. The semifinal output
will be tagged `semifinal-v2.0.0` only after the clean-clone, golden-result, PDF, and
package checks pass.

