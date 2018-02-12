/* -*- mode: espresso; espresso-indent-level: 8; indent-tabs-mode: t -*- */
/* vim: set softtabstop=2 shiftwidth=2 tabstop=2 expandtab: */

(function(CATMAID) {

  "use strict";

  const CONTROLS_SPACE = '   ';
  const COORDS_TOLERANCE = 1.5;

  const ConnectorPeruser = function() {
    this.widgetID = this.registerInstance();
    this.idPrefix = `connector-peruser${this.widgetID}-`;

    CATMAID.skeletonListSources.updateGUI();

    this.cache = {};
    this.connectorSet = new Set();

    this.oTable = null;

    this.rowIdx = 0;
  };

  $.extend(ConnectorPeruser.prototype, new InstanceRegistry());

  ConnectorPeruser.prototype.getName = function() {
    return 'Connector Peruser ' + this.widgetID;
  };

  ConnectorPeruser.prototype.updateConnectorCache = function() {
    const self = this;
    return CATMAID.fetch(`${project.id}/connector/info`, 'POST', {cids: Array.from(self.connectorSet)})
      .then(function(result) {
        self.cache = result.reduce(function(obj, row) {
          obj[row[0]] = {x: row[1][0], y: row[1][1], z: row[1][2]};
          return obj;
        }, {});
        return self.cache;
      });
  };

  function areSameCoords(coords1, coords2) {
    for (let dim of ['x', 'y', 'z']) {
      if (Math.abs(coords1[dim] - coords2[dim]) > COORDS_TOLERANCE) {
        return false;
      }
    }
    return true;
  }

  ConnectorPeruser.prototype.update = function () {
    const self = this;
    return this.updateConnectorCache()
      .then(
        function(cache){
          const thisRow = self.oTable.row(self.rowIdx);
          if (!areSameCoords(self.cache[thisRow.data().connectorID], thisRow.data())) {
            thisRow.invalidate();
          }
          const searchStr = document.getElementById(self.idPrefix + 'hide').checked ? 'false' : '';
          self.oTable.column(1).search(searchStr).draw();
          return cache;
        }
      );
  };

  ConnectorPeruser.prototype.nextRowIdx = function () {
    const self = this;
    let counter = 0;
    const total = this.oTable.data().length;
    return this.update().then(
      function(cache) {
        let newRowIdx = self.rowIdx;
        while (true) {
          counter++;
          if (counter >= total) {
            self.setRowIdx(0);
            return;
          }

          if (self.rowIdx >= total) {
            newRowIdx = 0;
          }

          const rowData = self.oTable.row(newRowIdx).data();

          if (areSameCoords(rowData, self.cache[rowData.connectorID])) {
            return self.setRowIdx(newRowIdx);
          } else {
            newRowIdx++;
          }
        }
      }
    );
  };

  ConnectorPeruser.prototype.getAndMoveToIndex = function() {
    const self = this;
    this.nextRowIdx().then(self.moveToIndex.bind(self));
  };

  ConnectorPeruser.prototype.setRowIdx = function(rowIdx) {
    $(this.oTable.row(this.rowIdx).node()).css('font-weight', '');
    this.rowIdx = rowIdx;
    $(this.oTable.row(rowIdx).node()).css('font-weight', 'bold');
    return rowIdx;
  };

  ConnectorPeruser.prototype.moveToIndex = function(rowIdx) {
    const rowData = this.oTable.row(rowIdx).data();
    const stackViewer = project.getStackViewers()[0];
    stackViewer.moveToProject(
      rowData.z, rowData.y, rowData.x,
      stackViewer.primaryStack.stackToProjectSX(stackViewer.s)
    );
  };

  ConnectorPeruser.prototype.getWidgetConfiguration = function() {
    const self = this;
    const tableID = this.idPrefix + 'datatable';
    return {
      helpText: 'Connector Peruser widget: Quickly see a list of connectors',
      controlsID: this.idPrefix + 'controls',
      createControls: function(controls) {
      //   const clear = document.createElement('input');
      //   clear.setAttribute("type", "button");
      //   clear.setAttribute("value", "Clear");
      //   clear.onclick = function() {
      //     Object.keys(self.cache).forEach(function(key){delete self.cache[key];});
      //     self.skeletonSource.clear();
      //   };
      //   controls.appendChild(clear);
      //
      //   const refresh = document.createElement('input');
      //   refresh.setAttribute("type", "button");
      //   refresh.setAttribute("value", "Refresh");
      //   refresh.onclick = function() {
      //     Object.keys(self.cache).forEach(function(key){delete self.cache[key];});
      //     self.update();
      //   };
      //   controls.appendChild(refresh);

        const fileSelect = document.createElement('input');
        fileSelect.type = 'file';
        fileSelect.name = 'myFile';
        controls.appendChild(fileSelect);

        // https://stackoverflow.com/a/36198572/2700168
        const fileImport = document.createElement('button');
        fileImport.innerText = 'Import';
        fileImport.onclick = function (event) {
          const files = fileSelect.files;
          if (files.length <= 0) {
            console.log('No files, returning false');
            return false;
          }

          var fr = new FileReader();

          fr.onload = function(e) {
            const result = JSON.parse(e.target.result);

            self.oTable.rows.add(result.map(function (item) {
              self.connectorSet.add(item.connector_id);
              return {
                connectorID: item.connector_id,
                x: item.x,
                y: item.y,
                z: item.z,
              };
            }));
            self.update();
          };

          fr.readAsText(files.item(0));
        };
        controls.appendChild(fileImport);

        controls.appendChild(document.createTextNode(CONTROLS_SPACE));

        const hideMovedCb = document.createElement('input');
        hideMovedCb.id = self.idPrefix + 'hide';
        hideMovedCb.type = 'checkbox';
        hideMovedCb.checked = false;
        hideMovedCb.onchange = self.update.bind(self);

        const hideMovedLabel = document.createElement('label');
        hideMovedLabel.title = 'Hide moved connectors in table';
        hideMovedLabel.appendChild(document.createTextNode('Hide moved: '));
        hideMovedLabel.appendChild(hideMovedCb);
        controls.appendChild(hideMovedLabel);

        const nextButton = document.createElement('button');
        nextButton.innerText = 'Next';
        nextButton.classList.add('connector-peruser-next');
        nextButton.id = self.idPrefix + 'next';
        nextButton.onclick = self.getAndMoveToIndex.bind(self);
        controls.appendChild(nextButton);
      },
      contentID: this.idPrefix + 'content',
      createContent: function(container) {
        //language=HTML
        container.innerHTML = `
          <table cellpadding="0" cellspacing="0" border="0" class="display" id="${tableID}"> 
            <thead> 
              <tr> 
                <th>connector ID
                  <input type="text" name="searchConnId" id="${self.idPrefix}search-conn-id"
                    value="Search" class="search_init"/></th>
                <th>moved</th> 
                <th>x</th> 
                <th>y</th> 
                <th>z</th> 
              </tr> 
            </thead> 
            <tfoot> 
              <tr> 
                <th>connector ID</th>
                <th>moved</th> 
                <th>x</th> 
                <th>y</th> 
                <th>z</th> 
              </tr> 
            </tfoot> 
            <tbody> 
            </tbody> 
          </table>
          
          <br>
          
          </div>
        `;
},
      init: self.init.bind(self)
    };
  };

  function round1dp(data, type, row, meta) {
    if (type === 'display') {
      return data.toFixed(1);
    } else {
      return data;
    }
  }

  /**
   * Initialise the widget.
   *
   */
  ConnectorPeruser.prototype.init = function() {
    const self = this;
    const tableID = this.idPrefix + 'datatable';

    const $table = $('#' + tableID);

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
          data: 'connectorID',
          render: Math.floor,
          orderable: true,
          searchable: true,
          className: "center"
        },
        {
          data: 'moved',
          render: function (data, type, row, meta) {
            const isLoaded = self.cache[row.connectorID] !== undefined;
            const hasMoved = isLoaded && !areSameCoords(row, self.cache[row.connectorID]);
            if (type === 'display' || type === 'filter') {
              return String(hasMoved);
            }
            return hasMoved;
          },
          orderable: true,
          searchable: true,
          className: "center"
        },
        {
          data: 'x',
          render: round1dp,
          orderable: true,
          className: "center"
        },
        {
          data: 'y',
          render: round1dp,
          orderable: true,
          className: "center"
        },
        {
          data: 'z',
          render: round1dp,
          orderable: true,
          className: "center"
        },
      ]
    });

    const exactNumSearch = function(event) {
      if (event.which == 13) {
        event.stopPropagation();
        event.preventDefault();
        // Filter with a regular expression
        const filterValue = event.currentTarget.value;
        const regex = filterValue === '' ? '' : `^${filterValue}$`;

        self.oTable
          .column(event.currentTarget.closest('th'))
          .search(regex, true, false)
          .draw();
      }
    };

    $(`#${self.idPrefix}search-conn-id`).keydown(exactNumSearch);

    const $headerInput = $table.find('thead input');

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
      const rowData = self.oTable.row(this).data();
      const stackViewer = project.getStackViewers()[0];
      stackViewer.moveToProject(
        rowData.z, rowData.y, rowData.x,
        stackViewer.primaryStack.stackToProjectSX(stackViewer.s)
      );
      self.setRowIdx(self.oTable.row(this).index());
    });
  };

  /**
   * Given arrays of keys and values, create an object {keys_1: values_1, keys_2: values_2} and so on.
   *
   * @param keys
   * @param values
   * @return {{}}
   */
  const objZip = function(keys, values) {
    const obj = {};
    for (let i = 0; i < Math.min(keys.length, values.length); i++) {
      obj[keys[i]] = values[i];
    }
    return obj;
  };

  ConnectorPeruser.prototype.destroy = function() {
    this.unregisterInstance();
  };

  CATMAID.registerWidget({
    name: 'Connector Peruser',
    description: 'Quickly view and move connector nodes',
    key: 'connector-peruser',
    creator: ConnectorPeruser
  });

})(CATMAID);
