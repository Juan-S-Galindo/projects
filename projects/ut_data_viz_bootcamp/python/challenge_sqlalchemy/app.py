import datetime as dt
import os

import numpy as np
import pandas as pd
import sqlalchemy
from flask import Flask, jsonify
from sqlalchemy import create_engine, func
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session

#################################################
# Database Setup
#################################################
engine = create_engine(
    f"sqlite:////{os.getcwd()}/projects/ut_data_viz_bootcamp/python/challenge_sqlalchemy/Resources/hawaii.sqlite"
)

# reflect an existing database into a new model
Base = automap_base()

# reflect the tables
Base.prepare(engine, reflect=True)

# Save references to each table.
measurement = Base.classes.measurement

station = Base.classes.station

#################################################
# Flask Setup
#################################################
app = Flask(__name__)

#################################################
# Flask Routes
#################################################


@app.route("/")
def welcome():
    """List all available api routes."""
    return (
        "<ul>"
        f"<li>Available Routes:<br/></li>"
        f"<li>/api/v1.0/precipitation<br/></li>"
        f"<li>/api/v1.0/stations<br/></li>"
        f"<li>/api/v1.0/tobs<br/></li>"
        f"<li>/api/v1.0/<start><br/></li>"
        f"<li>/api/v1.0/<start>/<end><br/></li>"
        "</ul>"
    )


@app.route("/api/v1.0/precipitation")
def precipitation():
    session = Session(engine)

    # Convert the query results to a dictionary using `date` as the key and `prcp` as the value.

    precipitation_data = (
        session.query(measurement.date, measurement.prcp)
        .order_by(measurement.date)
        .all()
    )

    precipitation_dict = {}

    for date, prcp in precipitation_data:
        if date not in precipitation_dict.keys():
            precipitation_dict[date] = []

        else:
            precipitation_dict[date].append(prcp)

    session.close()
    # Return the JSON representation of your dictionary.
    precipitation_dict

    return jsonify(precipitation_dict)


@app.route("/api/v1.0/stations")
def stations():
    session = Session(engine)

    # Return a JSON list of stations from the dataset.

    stationsActivity = (
        session.query(measurement.station, func.count(measurement.station))
        .group_by(measurement.station)
        .order_by(func.count(measurement.station).desc())
        .all()
    )

    session.close()
    stationsList = [i[0] for i in stationsActivity]

    return jsonify(stationsList)


@app.route("/api/v1.0/tobs")
def temperature():
    session = Session(engine)

    # Query the dates and temperature observations of the most active station for the last year of data.

    startingDate = (
        pd.to_datetime(list(session.query(measurement.date).all())[-1][0])
        - dt.timedelta(days=365)
    ).strftime("%Y-%m-%d")
    mostActiveStation = (
        session.query(measurement.station, func.count(measurement.station))
        .group_by(measurement.station)
        .order_by(func.count(measurement.station).desc())
        .all()[0][0]
    )

    twelveMonthDataTempStation = (
        session.query(measurement.date, measurement.tobs)
        .filter(measurement.date >= startingDate)
        .filter(measurement.station == mostActiveStation)
        .order_by(measurement.date)
        .all()
    )

    session.close()
    # Return a JSON list of temperature observations (TOBS) for the previous year.
    tempList = [i[1] for i in twelveMonthDataTempStation]

    return jsonify(tempList)


# Return a JSON list of the minimum temperature, the average temperature, and the max temperature for a given start or start-end range.


@app.route("/api/v1.0/<start>")  # yyyy-month-day
def tempStartRange(start):
    session = Session(engine)

    # When given the start only, calculate `TMIN`, `TAVG`, and `TMAX` for all dates greater than and equal to the start date.

    tempStartRange_func = (
        session.query(
            func.min(measurement.tobs),
            func.max(measurement.tobs),
            func.avg(measurement.tobs),
        )
        .filter(measurement.date >= start)
        .all()
    )

    session.close()
    tempStartRange_list = list(np.ravel(tempStartRange_func))

    return jsonify(tempStartRange_list)


@app.route("/api/v1.0/<start>/<end>")  # yyyy-month-day
def tempStartEndRange(start, end):
    session = Session(engine)

    # When given the start and the end date, calculate the `TMIN`, `TAVG`, and `TMAX` for dates between the start and end date inclusive.

    tempStartEndRange_func = (
        session.query(
            func.min(measurement.tobs),
            func.max(measurement.tobs),
            func.avg(measurement.tobs),
        )
        .filter(measurement.date >= start)
        .filter(measurement.date <= end)
        .all()
    )

    session.close()
    tempStartEndRange_list = list(np.ravel(tempStartEndRange_func))

    return jsonify(tempStartEndRange_list)


if __name__ == "__main__":
    app.run(debug=True)
