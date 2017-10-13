/* -*- mode: espresso; espresso-indent-level: 8; indent-tabs-mode: t -*- */
/* vim: set softtabstop=2 shiftwidth=2 tabstop=2 expandtab: */

(function(CATMAID) {

  "use strict";

  var CACHE_TIMEOUT = 30*60*1000;  // 30 minutes
  var URL_BASE = '/ext/synapsesuggestor';

  var CONSTRAINT_RANGES = {
    uncertainty: {
      min: 0,
      max: 1
    },
    sizePx: {
      min: 1,
      max: 10000
    },
    slices: {
      min: 1,
      max: 20
    },
    contactPx: {
      min: 1,
      max: 800
    }
  };


  var SynapseDetectionTable = function() {
    this.widgetID = this.registerInstance();
    this.idPrefix = `synapse-detection-table${this.widgetID}-`;

    var update = this.update.bind(this);

    /**
     * Skeleton source which is registered and other widgets can use
     */
    this.skeletonSource = new CATMAID.BasicSkeletonSource(this.getName(), {
      handleAddedModels: update,
      handleChangedModels: update,
      handleRemovedModels: update,
    });

    CATMAID.skeletonListSources.updateGUI();

    /**
     *   {
     *     skeletonID1: {
     *       'detections': {
     *         'timestamp': timestamp,
     *         'results': [
     *           {
     *             'detectedSynapseID': synID,
     *             'coords': {
     *               'x': x,
     *               'y': y,
     *               'z': z,
     *             },
     *             'bounds': {}
     *             'sizePx': sum of all pixel counts,
     *             'slices': 1,
     *             'uncertainty': mean uncertainty across all slices,
     *             'nodeID': first node encountered,
     *             'skelID': skeletonID
     *             'associatedConnIDs': Set,
     *             'intersectingConnectorEdges': []
     *           },
     *           {}
     *         ]
     *       },
     *       'connectors': {
     *         'timestamp': timestamp,
     *         'results': [
     *           {
     *             'connID': connID,
     *             'relationType': 'presynaptic_to'/'postsynaptic_to'
     *           },
     *           {}
     *         ]
     *       }
     *     },
     *     skeletonID2: {}
     *   }
     *
     * @type {{}}
     */
    this.cache = {};

    this.oTable = null;

    this.workflowInfoOptions = null;
    this.workflowInfo = null;
  };

  $.extend(SynapseDetectionTable.prototype, new InstanceRegistry());

  SynapseDetectionTable.prototype.getName = function() {
    return 'Synapse Detection Table ' + this.widgetID;
  };

  /**
   * Convert an ISO-8601 UTC time string into a local time string of format 'YYYY-mm-dd HH:MM'.
   *
   * @param utcStr
   */
  var utcStrToLocalTime = function(utcStr) {
    var d = new Date(utcStr);
    var year, month, day, hour, minute;
    year = d.getFullYear();
    month = String(d.getMonth()+1).padStart(2, 0);
    day = String(d.getDate()).padStart(2, 0);
    hour = String(d.getHours()).padStart(2, 0);
    minute = String(d.getMinutes()).padStart(2, 0);
    return `${year}-${month}-${day} ${hour}:${minute}`;
  };

  /**
   * Finds currently selected algorithm combination in the GUI select box and sets this.workflowInfo to be the
   * option in this.workflowInfoOptions which matches the selected option. Also returns that workflowInfo. If this
   * fails, the first (i.e. most recent) workflow is selected.
   *
   * @return {*|null}
   */
  SynapseDetectionTable.prototype.setWorkflowInfoFromSelect = function() {
    var value = document.getElementById(this.idPrefix + 'algo-select').value;
    for (var workflowInfo of this.workflowInfoOptions) {
      if (`${workflowInfo.detection_algo_hash}-${workflowInfo.association_algo_hash}` === value) {
        this.workflowInfo = workflowInfo;
        var flag = true;
        break;
      }
    }
    if (!flag) {
      this.workflowInfo = this.workflowInfo || this.workflowInfoOptions[0]
    }

    return this.workflowInfo;
  };

  /**
   * Populates the algorithm select box with the algorithm combinations in this.workflowInfoOptions.
   */
  SynapseDetectionTable.prototype.repopulateAlgoSelect = function() {
    var self = this;

    var select = document.getElementById(self.idPrefix + 'algo-select');
    while (select.lastChild) {
      select.removeChild(select.lastChild);
    }

    if (!self.workflowInfo){
      self.workflowInfo = this.workflowInfoOptions[0];
    }

    this.workflowInfoOptions.forEach(function(item, i) {
      var option = document.createElement("option");
      option.text = `${item.detection_algo_hash.slice(0, 7)} (${utcStrToLocalTime(item.detection_algo_date)}) & ` +
        `${item.association_algo_hash.slice(0, 7)} (${utcStrToLocalTime(item.association_algo_date)})`;
      option.value = `${item.detection_algo_hash}-${item.association_algo_hash}`;
      option.title = `Detection: ${item.detection_algo_notes}\nAssociation: ${item.association_algo_notes}`;

      if (i === 0) {
        option.defaultSelected = true;
      }
      if (option.value === `${self.workflowInfo.detection_algo_hash}-${self.workflowInfo.association_algo_hash}`) {
        option.selected = true;
      }
      select.appendChild(option);
    });
    self.setWorkflowInfoFromSelect()
  };

  SynapseDetectionTable.prototype.getWidgetConfiguration = function() {
    var self = this;
    var tableID = this.idPrefix + 'datatable';
    return {
      helpText: 'Synapse Detection Table widget: See automatically detected synapses for given skeleton(s)',
      controlsID: this.idPrefix + 'controls',
      createControls: function(controls) {
        var sourceControls = document.createElement('label');
        sourceControls.title = '0 skeletons selected';
        sourceControls.id = self.idPrefix + 'source-controls';
        controls.append(sourceControls);

        var sourceSelect = CATMAID.skeletonListSources.createSelect(this.skeletonSource,
          [this.skeletonSource.getName()]);
        sourceControls.appendChild(sourceSelect);

        var add = document.createElement('input');
        add.setAttribute("type", "button");
        add.setAttribute("value", "Add");
        add.onclick = function() {
          self.skeletonSource.loadSource.bind(self.skeletonSource)();
        };
        sourceControls.appendChild(add);

        var clear = document.createElement('input');
        clear.setAttribute("type", "button");
        clear.setAttribute("value", "Clear");
        clear.onclick = function() {
          Object.keys(self.cache).forEach(function(key){delete self.cache[key];});
          self.skeletonSource.clear();
        };
        sourceControls.appendChild(clear);

        var refresh = document.createElement('input');
        refresh.setAttribute("type", "button");
        refresh.setAttribute("value", "Refresh");
        refresh.onclick = function() {
          Object.keys(self.cache).forEach(function(key){delete self.cache[key];});
          self.update();
        };
        controls.appendChild(refresh);

        var algoLabel = document.createElement('label');
        algoLabel.appendChild(document.createTextNode('Algorithms:'));
        algoLabel.title = 'Algorithm combination used to detect synapses and associate them with skeletons';
        controls.appendChild(algoLabel);

        var algoSelect = document.createElement('select');
        algoSelect.id = self.idPrefix + 'algo-select';
        algoSelect.addEventListener('change', self.update.bind(self, true));
        algoLabel.appendChild(algoSelect);

        var toleranceLabel = document.createElement('label');
        toleranceLabel.appendChild(document.createTextNode('Tolerance (nm):'));
        toleranceLabel.title = '2D spatial tolerance, in nm, for determining whether a connector edge is associated' +
          ' with a synapse';
        controls.appendChild(toleranceLabel);

        var toleranceInput = document.createElement('input');
        toleranceInput.id = self.idPrefix + 'tolerance';
        toleranceInput.type = 'text';
        toleranceInput.size = 4;
        toleranceInput.pattern = '\d*\.?\d*';
        toleranceInput.value = 0;
        toleranceInput.min = 0;
        toleranceInput.addEventListener('change', self.update.bind(self, true));
        toleranceLabel.append(toleranceInput);

        var jsonButton = document.createElement('button');
        jsonButton.innerText = 'Download cache dump';
        jsonButton.onclick = function() {
          saveAs(new Blob([JSON.stringify(self.cache, null, 2)], {type: 'text/json'}), 'syndetcache.json');
        };
        controls.appendChild(jsonButton);

      },
      contentID: this.idPrefix + 'content',
      createContent: function(container) {
        //language=HTML
        container.innerHTML = `
          <table cellpadding="0" cellspacing="0" border="0" class="display" id="${tableID}"> 
            <thead> 
              <tr> 
                <th>detected synapse ID</th> 
                <th>skeleton ID 
                  <input type="text" name="searchSkelId" id="${self.idPrefix}search-skel-id" 
                    value="Search" class="search_init"/> 
                </th> 
                <th>uncertainty</th> 
                <th>size (px)</th> 
                <th>contact area (px)</th> 
                <th>slices</th> 
                <th>associated connectors <input type="text" id="${self.idPrefix}search-conn-id"
                  value="Search" class="search_init"></th> 
              </tr> 
            </thead> 
            <tfoot> 
              <tr> 
                <th>detected synapse ID</th> 
                <th>skeleton ID</th> 
                <th>uncertainty</th> 
                <th>size (px)</th> 
                <th>contact area (px)</th> 
                <th>slices</th> 
                <th>associated connectors</th> 
              </tr> 
            </tfoot> 
            <tbody> 
            </tbody> 
          </table>
          
          <br>
          
          <div id="${self.idPrefix}constraints">
            <div class="uncertainty">
              <label>
                Uncertainty: <a class="min">unknown</a> - <a class="max">unknown</a>
              </label>
            
              <div class="constraint-slider"></div>
            </div>
            
            <br>
            
            <div class="sizePx">
              <label>
                Size (px): <a class="min">unknown</a> - <a class="max">unknown</a>
              </label>
            
              <div class="constraint-slider"></div>
            </div>
          
            <br>
          
            <div class="slices">
              <label>
                Slices: <a class="min">unknown</a> - <a class="max">unknown</a>
              </label>
            
              <div class="constraint-slider"></div>
            </div>
            
            <div class="contactPx">
              <label>
                Contact area (px): <a class="min">unknown</a> - <a class="max">unknown</a>
              </label>
            
              <div class="constraint-slider"></div>
            </div>
          </div>
          
          <br>
          
          <table>
            <caption>Analysis results</caption>
            <tr><td>Total traced</td><td id="${self.idPrefix}total-traced">0</td></tr>
            <tr><td>Total detected</td><td id="${self.idPrefix}total-detected">0</td></tr>
            <tr><td>Connectors associated with detected</td><td id="${self.idPrefix}traced-and-detected">0</td></tr>
            <tr><td>Detected associated with connectors</td><td id="${self.idPrefix}detected-and-traced">0</td></tr>
            <tr><td>Possible double-annotated</td><td id="${self.idPrefix}double-annotated">0</td></tr>
            <tr><td>Possible stitching error</td><td id="${self.idPrefix}stitch-error">0</td></tr>
            <tr><td>Detection precision</td><td id="${self.idPrefix}detection-precision">0</td></tr>
            <tr><td>Detection recall</td><td id="${self.idPrefix}detection-recall">0</td></tr>
            <tr><td>F1 score</td><td id="${self.idPrefix}f1-score">0</td></tr>
            <tr><td>F2 score (reward recall)</td><td id="${self.idPrefix}f2-score">0</td></tr>
            <tr><td>F0.5 score (reward precision)</td><td id="${self.idPrefix}f05-score">0</td></tr>
          </table>
          
          <br>
          
          <div id="${self.idPrefix}sweep-constants">
            <label>Uncertainty: <input class="uncertainty" type="number"></label>
            <label>Size: <input class="sizePx" type="number"></label>
            <label>Slices: <input class="slices" type="number"></label>
            <label>Contact area: <input class="contactPx" type="number"></label>
          </div>
          
          <br>
          
          <div id="${self.idPrefix}plots">
            <label>Download results: <input type="checkbox" class="download-checkbox"></label>
            <label>Bins: <input type="number" class="bins-input" value="10" min="2"></label>
            <br>
            <button class="uncertainty">Plot precision/recall for uncertainty</button>
            <button class="sizePx">Plot precision/recall for synapse size</button>
            <button class="slices">Plot precision/recall for synapse slices</button>
            <button class="contactPx">Plot precision/recall for contact area</button> 
            <br>
            <button class="compare">Compare precision-recalls</button>
            <div style="width:1000px; height:1000px" class="plot"></div>
          </div>
        `;
},
      init: self.init.bind(self)
    };
  };

  /**
   * Get the list of valid workflows (for this project and stack), cache it, populate the algorithm select element and
   * select the first (i.e. most recent) for use with the table.
   *
   * @return {Promise.<*>}
   */
  SynapseDetectionTable.prototype.getWorkflowInfo = function() {
    if (this.workflowInfo) {
      return Promise.resolve(this.workflowInfo)
    } else {
      var self = this;
      var stackId = project.getStackViewers()[0].primaryStack.id;
      return CATMAID.fetch(`${URL_BASE}/analysis/${project.id}/workflow-info`, 'GET', {stack_id: stackId})
        .then(function(response) {
          self.workflowInfoOptions = response.workflows;
          self.workflowInfo = self.workflowInfo || response.workflows[0];
          self.repopulateAlgoSelect();
          return self.workflowInfo;
        })
    }
  };

  /**
   * Initialise the widget.
   *
   * Populate the algorithm select element, draw the table, and add listeners to buttons.
   */
  SynapseDetectionTable.prototype.init = function() {
    var self = this;
    var tableID = this.idPrefix + 'datatable';

    self.getWorkflowInfo();

    var $table = $('#' + tableID);

    this.oTable = $table.DataTable({
      // http://www.datatables.net/usage/options
      destroy: true,
      dom: '<"H"lrp>t<"F"ip>',
      serverSide: false,
      paging: true,
      lengthChange: true,
      autoWidth: false,
      pageLength: CATMAID.pageLengthOptions[0],
      lengthMenu: [CATMAID.pageLengthOptions, CATMAID.pageLengthLabels],
      jQueryUI: true,
      processing: true,
      deferRender: true,
      columns: [
        {
          data: 'detectedSynapseID',
          render: Math.floor,
          orderable: true,
          className: "center"
        },
        {
          data: 'skelID',
          render: Math.floor,
          orderable: true,
          searchable: true,
          className: "center"
        },
        {
          data: 'uncertainty',
          render: function (data, type, row, meta) {
            if (type === 'display') {
              return Math.round(data * 100) / 100;
            } else {
              return data;
            }
          },
          orderable: true,
          className: "center"
        },
        {
          data: 'sizePx',
          render: Math.floor,
          orderable: true,
          className: "center"
        },
        {
          data: 'contactPx',
          render: Math.floor,
          orderable: true,
          className: "center"
        },
        {
          data: 'slices',
          orderable: true,
          className: "center"
        },
        {
          data: 'associatedConnIDs',
          render: function (data, type, row, meta) {
            if (type === 'filter') {
              return ` ${Array.from(data).join(' ')} `;
            } else {
              return data.size;
            }
          },
          orderable: true,
          className: 'center'
        }
      ]
    });

    $(`#${self.idPrefix}search-conn-id`).keydown(function (event) {
      if (event.which == 13) {
        event.stopPropagation();
        event.preventDefault();
        // Filter with a regular expression
        var filter_connID = event.currentTarget.value;
        self.oTable
          .column(event.currentTarget.closest('th'))
          .search(` ${filter_connID} `, false, false)
          .draw();
      }
    });

    var $headerInput = $table.find('thead input');

    // prevent sorting the column when focusing on the search field
    $headerInput.click(function (event) {
      event.stopPropagation();
    });

    // remove the 'Search' string when first focusing the search box
    $headerInput.focus(function () {
      if (this.className === "search_init") {
        this.className = "";
        this.value = "";
      }
    });

    $table.on("dblclick", "tbody tr", function () {
      var rowData = self.oTable.row(this).data();
      var coords = rowData.coords;

      var stackViewer = project.getStackViewers()[0];

      stackViewer.moveToPixel(
        'z' in coords ? coords.z : stackViewer.z,
        'y' in coords ? coords.y : stackViewer.y,
        'x' in coords ? coords.x : stackViewer.x,
        's' in coords ? coords.s : stackViewer.s
      );

    });

    var $constraints = $(`#${self.idPrefix}constraints`);
    self.createConstraintSlider($constraints.find('.uncertainty'), 0, 1, 0.01);
    self.createConstraintSlider($constraints.find('.sizePx'), 0, 20000, 1);
    self.createConstraintSlider($constraints.find('.slices'), 0, 20, 1);
    self.createConstraintSlider($constraints.find('.contactPx'), 0, 1000, 1);

    $constraints.find('.constraint-slider').css({
      width: '50%',
      position: 'relative',
      left: '15px'
    });

    $constraints.find('.ui-slider-range').css('background', '#0000ff');

    var $plots = $(`#${self.idPrefix}plots`);
    var plotContainer = $plots.find('.plot')[0];
    var $downloadCheckbox = $plots.find('.download-checkbox')[0];
    var $binsInput = $plots.find('.bins-input')[0];

    var $sweepConstants = $(`#${self.idPrefix}sweep-constants`);

    var getPrecisionRecallConstants = function () {
      var obj = {};
      var val;

      // uncertainty
      val = Number($sweepConstants.find('.uncertainty').val());
      if (val) {
        obj.uncertainty = {max: [val]};
      }

      // sizePx
      val = Number($sweepConstants.find('.sizePx').val());
      if (val) {
        obj.sizePx = {min: [val]};
      }

      // slices
      val = Number($sweepConstants.find('.slices').val());
      if (val) {
        obj.slices = {min: [val]};
      }

      return obj;
    };

    var plotFnFactory = function (attribute) {
      return function (event) {
        emptyNode(plotContainer);
        var constraints = getPrecisionRecallConstants();
        var bins = Number($binsInput.value);
        if (attribute === 'uncertainty') {
          constraints.uncertainty = {
            min: linspace(CONSTRAINT_RANGES.uncertainty.min, CONSTRAINT_RANGES.uncertainty.min, bins)
          }
        } else {
          constraints[attribute] = {
            max: linspace(CONSTRAINT_RANGES[attribute].min, CONSTRAINT_RANGES[attribute].max, bins, true)
          }
        }

        self.plotConstraintSweep(
          plotContainer,
          self.skeletonSource.getSelectedSkeletons(),
          constraints,
          attribute,
          $downloadCheckbox.checked
        );
      };
    };

    $plots.on('click', '.uncertainty', plotFnFactory('uncertainty'));
    $plots.on('click', '.sizePx', plotFnFactory('sizePx'));
    $plots.on('click', '.slices', plotFnFactory('slices'));
    $plots.on('click', '.contactPx', plotFnFactory('contactPx'));

    $plots.on('click', '.compare', function(event) {
      emptyNode(plotContainer);
      self.plotAllPrecRecCurves(
        plotContainer,
        self.skeletonSource.getSelectedSkeletons(),
        Number($binsInput.value)
      );
    })
  };

  /**
   * Remove all child nodes of given HTML element.
   *
   * @param element
   * @return {*}
   */
  var emptyNode = function(element) {
    while (element.lastChild) {
      element.removeChild(element.lastChild);
    }
    return element;
  };

  /**
   * Return an array of numbers from 'start' to 'stop' (inclusive), of length 'count'. If 'round' is true, round each
   * one. Prevents duplicates, so length may be smaller than count.
   *
   * @param start
   * @param stop
   * @param count
   * @param round
   * @return {[*]}
   */
  var linspace = function(start, stop, count, round) {
    var out = [start];
    var step = (stop - start) / (count-1);
    var previous = start;
    for (var i = 1; i < count-1; i++) {
      start += step;
      var value = round ? Math.round(start) : start;
      if (value !== previous && value !== stop) {
        out.push(value)
      }
      previous = value;
    }
    out.push(stop);  // account for float imprecision

    return out;
  };

  /**
   *
   * @param $container : jQuery object wrapping div containing labels and slider div
   * @param min
   * @param max
   * @param step
   */
  SynapseDetectionTable.prototype.createConstraintSlider = function($container, min, max, step) {
    var self = this;

    var $slider = $container.find('.constraint-slider');
    $slider.slider({
      range: true,
      min: min,
      max: max,
      values: [min, max],
      step: step,
      slide: function(event, ui) {
        $container.find('.min').text(ui.values[0]);
        $container.find('.max').text(ui.values[1]);
      },
      change: function(event, ui) {
        self.populateAnalysisResults();
      }
    });
    $container.find('.min').text($slider.slider('values', 0));
    $container.find('.max').text($slider.slider('values', 1));
  };

  SynapseDetectionTable.prototype.setSkelSourceText = function() {
    var count = this.skeletonSource.getNumberOfSkeletons();
    var element = document.getElementById(this.idPrefix + 'source-controls');
    element.title = `${count} skeleton${count === 1 ? '' : 's'} selected`;
  };

  var connResponseToConnEdgeInfo = function(connEdgeResponse) {
    return {
      connID: connEdgeResponse[0],
      coords: {
        x: connEdgeResponse[1],
        y: connEdgeResponse[2],
        z: connEdgeResponse[3]
      },
      confidence: connEdgeResponse[4],
      userID: connEdgeResponse[6],
      treenodeID: connEdgeResponse[7]
    };
  };

  SynapseDetectionTable.prototype.getConnectorsForSkel = function(skelID) {
    var self = this;

    if (this.cache[skelID]) {
      if (this.cache[skelID].connectors && Date.now() - this.cache[skelID].connectors.timestamp <= CACHE_TIMEOUT) {
        return Promise.resolve(this.cache[skelID].connectors.results);
      }
    } else {
      this.cache[skelID] = {detections: {}, connectors: {}};
    }

    var promises = ['presynaptic_to', 'postsynaptic_to'].map(function(relationType) {
      return CATMAID.fetch(
        project.id + '/connectors', 'GET', {skeleton_ids: [skelID], relation_type: relationType, with_tags: false}
      ).then(function(response) {
        var outObj = response.links.reduce(function(obj, row) {
          obj[row[1]] = {connID: row[1], relationType: relationType};
          return obj;
        }, {});

        return Object.keys(outObj).map(function(key){return outObj[key];});
      });
    });

    return Promise.all(promises).then(function(resultsPair) {
      self.cache[skelID].connectors.results = resultsPair[0].concat(resultsPair[1]);
      return self.cache[skelID].connectors.results;
    });
  };

  /**
   * Given arrays of keys and values, create an object {keys_1: values_1, keys_2: values_2} and so on.
   *
   * @param keys
   * @param values
   * @return {{}}
   */
  var objZip = function(keys, values) {
    var obj = {};
    for (var i = 0; i < Math.min(keys.length, values.length); i++) {
      obj[keys[i]] = values[i]
    }
    return obj;
  };

  SynapseDetectionTable.prototype.getSynapsesForSkel = function(skelID) {
    var self = this;

    if (this.cache[skelID]) {
      if (this.cache[skelID].detections && Date.now() - this.cache[skelID].detections.timestamp <= CACHE_TIMEOUT) {
        return Promise.resolve(this.cache[skelID].detections.results);
      }
    } else {
      this.cache[skelID] = {detections: {}, connectors: {}};
    }

    return CATMAID.fetch(
      `${URL_BASE}/analysis/${project.id}/skeleton-synapses`, 'GET',
      {skeleton_id: skelID, workflow_id: self.workflowInfo.workflow_id}
      ).then(function(response){
        return response.data.reduce(function (obj, responseRow) {
          var responseRowObj = objZip(response.columns, responseRow);
          obj[responseRowObj.synapse] = {
            detectedSynapseID: responseRowObj.synapse,
            coords: {
              x: responseRowObj.xs,
              y: responseRowObj.ys,
              z: responseRowObj.zs,
            },
            sizePx: responseRowObj.size_px,
            contactPx: responseRowObj.contact_px,
            slices: new Set(responseRowObj.z_slices).size,
            uncertainty: responseRowObj.uncertainty_avg,
            nodeIDs: new Set(responseRowObj.nodes),
            skelID: skelID,
            associatedConnIDs: new Set()
          };
          return obj;
        }, {});
      }).then(function (rowsObj) {
        var tolerance = Number(document.getElementById(self.idPrefix + 'tolerance').value);
        return CATMAID.fetch(
          `${URL_BASE}/analysis/${project.id}/intersecting-connectors`, 'POST',
          {workflow_id: self.workflowInfo.workflow_id, synapse_object_ids: Object.keys(rowsObj), tolerance: tolerance}
        ).then(function(response) {
          for (var responseRow of response.data) {
            var responseRowObj = objZip(response.columns, responseRow);
            rowsObj[responseRowObj.synapse_id].associatedConnIDs.add(responseRowObj.connector_id);
          }
          var rowsWithIntersecting = Object.keys(rowsObj)
            .sort(function(a, b) {return a - b;})
            .map(function(synID) {return rowsObj[synID]});

          self.cache[skelID].detections = {
            timestamp: Date.now(),
            results: rowsWithIntersecting
          };

          return rowsWithIntersecting;
        })
    });
  };

  SynapseDetectionTable.prototype.getConnectorsSynapsesForSkel = function(skelID) {
    var self = this;
    return Promise.all([self.getConnectorsForSkel(skelID), self.getSynapsesForSkel(skelID)])
      .then(function(resultsPair) {
        return {
          connectors: resultsPair[0],
          detections: resultsPair[1]
        };
      });
  };

  var fillOutConstraints = function(constraints) {
    if (!constraints) {
      constraints = {};
    }
    for (var constraintKey of ['uncertainty', 'sizePx', 'slices', 'contactPx']) {
      if (!constraints[constraintKey]) {
        constraints[constraintKey] = {};
      }

      if (typeof constraints[constraintKey].min === 'undefined') {
        constraints[constraintKey].min = -Infinity;
      }
      if (typeof constraints[constraintKey].max === 'undefined') {
        constraints[constraintKey].max = Infinity;
      }
    }

    return constraints;
  };

  /**
   * Constrain by uncertainty, size, slice count
   *
   * @param synInfo
   * @param constraints
   */
  var shouldSkipSynapse = function(synInfo, constraints){
    return (
      synInfo.uncertainty > constraints.uncertainty.max ||
      synInfo.uncertainty < constraints.uncertainty.min ||
      synInfo.sizePx > constraints.sizePx.max ||
      synInfo.sizePx < constraints.sizePx.min ||
      synInfo.slices > constraints.slices.max ||
      synInfo.slices < constraints.slices.min ||
      synInfo.contactPx > constraints.contactPx.max ||
      synInfo.contactPx < constraints.contactPx.min
    );
  };

  /**
   * Get a number of useful analyses of the synapse detection results compared to the manually traced results.
   *
   * Total count traced
   * Total count detected
   * Proportion traced which intersect detected
   * Proportion detected which have intersecting annotation
   * Possible doubly traced synapses (single detection has multiple associated connectors)
   * Possible stitching failures (single connector passes through >1 detected synapse)
   *
   * @param skelIDs
   * @param constraints
   * @return {Promise.<TResult>}
   */
  SynapseDetectionTable.prototype.analyse = function(skelIDs, constraints) {
    var self = this;

    constraints = fillOutConstraints(constraints);

    return Promise.all(skelIDs.map(self.getConnectorsSynapsesForSkel.bind(self)))
      .then(function(dataBySkel) {
        var results = {constraints: constraints};

        var data = dataBySkel.reduce(function(obj, resultsForSkel) {
          return {
            connectors: obj.connectors.concat(resultsForSkel.connectors),
            detections: obj.detections.concat(resultsForSkel.detections)
          };
        }, {connectors: [], detections: []});

        var connSet = data.connectors.reduce(function(set, connInfo) {
          return set.add(connInfo.connID);
        }, new Set());

        results.totalTraced = data.connectors.length;  // number of connectors
        results.totalDetected = 0;  // number of detected synapses (= length(unique(synapseIDs)))

        results.tracedAndDetected = 0;
        results.detectedAndTraced = 0;

        results.multiAnnotatedSynapses = 0;

        var detectedConns = new Map();

        for (var detection of data.detections) {
          if (shouldSkipSynapse(detection, constraints)) {
            continue;
          }

          results.totalDetected += 1;
          var intersection = connSet.intersection(detection.associatedConnIDs);

          if (intersection.size > 0) {
            results.detectedAndTraced += 1;
            for (var connID of intersection) {
              detectedConns.set(connID, (detectedConns.get(connID) || 0) + 1);
            }
          }

          if (detection.associatedConnIDs.size > 1) {
            results.multiAnnotatedSynapses += 1;
          }
        }

        results.tracedAndDetected = results.totalTraced;
        results.stitchingErrors = 0;
        for (var connector of data.connectors) {
          if (!detectedConns.has(connector.connID)) {
            results.tracedAndDetected -= 1;
          } else {
            results.stitchingErrors += detectedConns.get(connector.connID) - 1;
          }
        }

        // assumes traced as ground truth
        results.detectionPrecision = results.totalDetected ? results.detectedAndTraced / results.totalDetected : 1;
        results.detectionRecall = results.totalTraced ? results.tracedAndDetected / results.totalTraced : 1;

        results.f1 = fscore(results.detectionPrecision, results.detectionRecall, 1);
        results.f2 = fscore(results.detectionPrecision, results.detectionRecall, 2);
        results.f05 = fscore(results.detectionPrecision, results.detectionRecall, 0.5);

        return results;
      });
  };

  /**
   *
   * @param precision between 0 and 1
   * @param recall between 0 and 1
   * @param beta >0
   * @return {number}
   */
  var fscore = function(precision, recall, beta) {
    beta = beta || 1;
    return (1 * beta**2) * precision * recall / ((beta**2 * precision) + recall)
  };

  /**
   * Doesn't account for multiple-labelled synapses, stitching errors.
   *
   * @param skelIDs
   * @param constraints
   * @return {Promise.<TResult>}
   */
  SynapseDetectionTable.prototype.quickAnalyse = function(skelIDs, constraints) {
    var self = this;

    constraints = fillOutConstraints(constraints);

    return Promise.all(skelIDs.map(self.getConnectorsSynapsesForSkel.bind(self)))
      .then(function(dataBySkel) {
        var connSet = new Set();
        var detectedConns = new Set();
        var detectedSet = new Set();

        dataBySkel.forEach(function (resultsForSkel) {
          connSet.addAll(resultsForSkel.connectors.map(function(item) {return item.connID;}));
          for (var synapseInfo of resultsForSkel.detections) {
            if (shouldSkipSynapse(synapseInfo, constraints)) {
              continue;
            }
            detectedConns.addAll(synapseInfo.associatedConnIDs);
            detectedSet.add(synapseInfo.detectedSynapseID);
          }
        });

        return {
          constraints: constraints,
          totalTraced: connSet.size,
          totalDetected: detectedSet.size,
          tracedAndDetected: connSet.intersection(detectedConns).size,
        };
      });
  };

  SynapseDetectionTable.prototype.getAnalysisConstraints = function() {
    var self = this;
    var $constraints = $(`#${self.idPrefix}constraints`);
    var $uncertainty = $constraints.find('.uncertainty');
    var $sizePx = $constraints.find('.sizePx');
    var $slices = $constraints.find('.slices');
    var $contactPx = $constraints.find('.contactPx');
    return {
      uncertainty: {
        min: Number($uncertainty.find('.min').text()),
        max: Number($uncertainty.find('.max').text())
      },
      sizePx: {
        min: Number($sizePx.find('.min').text()),
        max: Number($sizePx.find('.max').text())
      },
      slices: {
        min: Number($slices.find('.min').text()),
        max: Number($slices.find('.max').text())
      },
      contactPx: {
        min: Number($contactPx.find('.min').text()),
        max: Number($contactPx.find('.max').text())
      }
    };
  };

  SynapseDetectionTable.prototype.populateAnalysisResults = function() {
    var self = this;

    var skels = self.skeletonSource.getSelectedSkeletons();
    var constraints = self.getAnalysisConstraints();

    self.analyse(skels, constraints)
      .then(function (analysisResults) {
        document.getElementById(self.idPrefix + 'total-traced').innerText = analysisResults.totalTraced;
        document.getElementById(self.idPrefix + 'total-detected').innerText = analysisResults.totalDetected;
        document.getElementById(self.idPrefix + 'traced-and-detected').innerText = analysisResults.tracedAndDetected;
        document.getElementById(self.idPrefix + 'detected-and-traced').innerText = analysisResults.detectedAndTraced;
        document.getElementById(self.idPrefix + 'double-annotated').innerText = analysisResults.multiAnnotatedSynapses;
        document.getElementById(self.idPrefix + 'stitch-error').innerText = analysisResults.stitchingErrors;
        document.getElementById(self.idPrefix + 'detection-precision').innerText = analysisResults.detectionPrecision;
        document.getElementById(self.idPrefix + 'detection-recall').innerText = analysisResults.detectionRecall;
        document.getElementById(self.idPrefix + 'f1-score').innerText = analysisResults.f1;
        document.getElementById(self.idPrefix + 'f2-score').innerText = analysisResults.f2;
        document.getElementById(self.idPrefix + 'f05-score').innerText = analysisResults.f05;
      });
  };

  var cartesianProductConstraints = function(constraintsArr, thisConstraintSet, allConstraintSets) {
    thisConstraintSet = thisConstraintSet || {};
    allConstraintSets = allConstraintSets || [];

    for (var constraintVal of constraintsArr[0][2]) {
      var newConstraintSet = Object.assign({}, thisConstraintSet);
      newConstraintSet[constraintsArr[0][0]] = newConstraintSet[constraintsArr[0][0]] || {};
      newConstraintSet[constraintsArr[0][0]][constraintsArr[0][1]] = constraintVal;
      if (constraintsArr.length < 2) {
        allConstraintSets.push(fillOutConstraints(newConstraintSet));
      } else {
        cartesianProductConstraints(constraintsArr.slice(1), newConstraintSet, allConstraintSets);
      }
    }

    return allConstraintSets;
  };

  var getConstraintsSweep = function(constraints) {
    var constraintsArr = [];  // [[constraint, end, arr], ...]

    for (var constraint of Object.keys(constraints).sort()) {
      for (var end of Object.keys(constraints[constraint]).sort()) {
        if (Array.isArray(constraints[constraint][end])) {
          constraintsArr.push([constraint, end, constraints[constraint][end]]);
        }
      }
    }

    return cartesianProductConstraints(constraintsArr);
  };

  SynapseDetectionTable.prototype.sweepConstraints = function(skelIDs, constraintsToSweep) {
    var self = this;
    var promises = getConstraintsSweep(constraintsToSweep).map(function(constraintsObj) {
      return self.analyse(skelIDs, constraintsObj);
    });
    return Promise.all(promises);
  };

  SynapseDetectionTable.prototype.plotConstraintSweep = function(container, skelIDs, constraintsToSweep, title, download) {
    title = title || '';

    this.sweepConstraints(skelIDs, constraintsToSweep)
      .then(function(analysisResults){
        if (download) {
          saveAs(new Blob([JSON.stringify(analysisResults, null, 2)], {type: 'text/json'}), 'analysisresults.json');
        }

        var precisionRecall = analysisResults.reduce(
          function(accumulator, currentValue){
            accumulator.y.push(currentValue.detectionPrecision);
            accumulator.x.push(currentValue.detectionRecall);
            return accumulator;
          },
          {y: [], x: [], type: 'lines+markers'}
        );

        Plotly.newPlot(
          container,
          [precisionRecall],
          {
            title: title,
            xaxis: {
              title: 'recall',
              showgrid: true,
              zeroline: true,
              range: [0, 1],
              showspikes: true
            },
            yaxis: {
              title: 'precision',
              showgrid: true,
              zeroline: true,
              range: [0, 1],
              showspikes: true
            }
          }
        );
      });
  };

  SynapseDetectionTable.prototype.plotAllPrecRecCurves = function(container, skelIDs, bins) {
    var self = this;
    var linePromises = Object.keys(CONSTRAINT_RANGES).map(function(constraintName){
      var constraintObj = {};
      if (constraintName === 'uncertainty') {
        constraintObj.uncertainty = {
          min: linspace(CONSTRAINT_RANGES.uncertainty.min, CONSTRAINT_RANGES.uncertainty.min, bins)
        }
      } else {
        constraintObj[constraintName] = {
          max: linspace(CONSTRAINT_RANGES[constraintName].min, CONSTRAINT_RANGES[constraintName].max, bins, true)
        }
      }

      return self.sweepConstraints(skelIDs, constraintObj).then(function(analysisResults) {
        return analysisResults.reduce(function(accumulator, currentValue){
            accumulator.y.push(currentValue.detectionPrecision);
            accumulator.x.push(currentValue.detectionRecall);
            return accumulator;
          }, {y: [], x: [], type: 'lines+markers', name: constraintName}
        );
      })
    });

    Promise.all(linePromises).then(function(lines) {
      Plotly.newPlot(
        container,
        lines,
        {
          title: 'Comparison',
          xaxis: {
            title: 'recall',
            showgrid: true,
            zeroline: true,
            range: [0, 1],
            showspikes: true
          },
          yaxis: {
            title: 'precision',
            showgrid: true,
            zeroline: true,
            range: [0, 1],
            showspikes: true
          }
        }
      );
    });
  };

  SynapseDetectionTable.prototype.update = function(forceRefresh) {
    var self = this;
    if (forceRefresh) {
      self.cache = {};
    }
    this.oTable.clear();

    this.getWorkflowInfo().then(function(){
      self.setWorkflowInfoFromSelect();
      return Promise.all(
        self.skeletonSource
          .getSelectedSkeletons()
          .map(self.getSynapsesForSkel.bind(self))
      ).then(function(rowsArr) {
        for (var rowObjs of rowsArr) {
          self.oTable.rows.add(rowObjs);
        }
        self.populateAnalysisResults();
        self.setSkelSourceText();
        self.oTable.draw();
      });
    });
  };

  SynapseDetectionTable.prototype.destroy = function() {
    this.skeletonSource.destroy();
    this.unregisterInstance();
  };

  CATMAID.registerWidget({
    name: 'Synapse Detection Table',
    description: 'View results of automated synapse detection',
    key: 'synapse-detection-table',
    creator: SynapseDetectionTable
  });

})(CATMAID);
